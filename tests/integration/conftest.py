# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import functools
import os
import platform
import re
import secrets
import subprocess
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Optional

import jubilant
import ldap
import psycopg
import pytest
import yaml

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
CERTIFICATE_PROVIDER_APP = "self-signed-certificates"
GLAUTH_UTILS_APP = METADATA["name"]
GLAUTH_APP = "glauth-k8s"
DB_APP = "postgresql-k8s"
TRAEFIK_CHARM = "traefik-k8s"
INGRESS_APP = "ingress"
INGRESS_URL_REGEX = re.compile(r"url:\s*(?P<ingress_url>\d{1,3}(?:\.\d{1,3}){3}:\d+)")
BASE_DN = "dc=glauth,dc=com"
BIND_DN = f"cn=serviceuser,ou=juju,{BASE_DN}"
BIND_PASSWORD = "mysecret"

StatusPredicate = Callable[[jubilant.Status], bool]


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options for model management and deployment control."""
    parser.addoption(
        "--keep-models",
        "--no-teardown",
        action="store_true",
        dest="no_teardown",
        default=False,
        help="Keep the model after the test is finished.",
    )
    parser.addoption(
        "--model",
        action="store",
        dest="model",
        default=None,
        help="The model to run the tests on.",
    )
    parser.addoption(
        "--no-deploy",
        "--no-setup",
        action="store_true",
        dest="no_setup",
        default=False,
        help="Skip deployment of the charm.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for test selection."""
    config.addinivalue_line("markers", "setup: tests that setup some parts of the environment")
    config.addinivalue_line(
        "markers", "teardown: tests that teardown some parts of the environment."
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Modify collected test items based on command-line options."""
    skip_setup = pytest.mark.skip(reason="no_setup provided")
    skip_teardown = pytest.mark.skip(reason="no_teardown provided")
    for item in items:
        if config.getoption("no_setup") and "setup" in item.keywords:
            item.add_marker(skip_setup)
        if config.getoption("no_teardown") and "teardown" in item.keywords:
            item.add_marker(skip_teardown)


def juju_model_factory(model_name: str) -> tuple[jubilant.Juju, bool]:
    """Create or attach to a Juju model configured for integration tests."""
    juju = jubilant.Juju()
    created = True
    try:
        juju.add_model(model_name, config={"logging-config": "<root>=INFO"})
    except jubilant.CLIError as e:
        if "already exists" not in e.stderr:
            raise
        created = False

    juju.model = model_name

    if created or os.getenv("CI"):
        arch_map = {
            "aarch64": "arm64",
            "arm64": "arm64",
            "x86_64": "amd64",
            "amd64": "amd64",
        }
        host_arch = arch_map.get(platform.machine().lower(), "amd64")
        juju.cli("set-model-constraints", f"arch={host_arch}")

    return juju, created


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest) -> Generator[jubilant.Juju, None, None]:
    """Create a temporary Juju model for integration tests."""
    model_name = request.config.getoption("--model") or f"test-glauth-utils-{secrets.token_hex(4)}"
    juju_, created = juju_model_factory(model_name)
    juju_.wait_timeout = 10 * 60

    try:
        yield juju_
    finally:
        if request.session.testsfailed:
            print(juju_.debug_log(limit=1000), end="")

        no_teardown = bool(request.config.getoption("--no-teardown"))
        keep_model = no_teardown or request.session.testsfailed > 0 or not created
        if not keep_model:
            with suppress(jubilant.CLIError):
                juju_.destroy_model(
                    model_name,
                    destroy_storage=True,
                    force=True,
                    timeout=600,
                )


def all_active(*apps: str) -> StatusPredicate:
    """Return a predicate that checks all given apps are active."""
    return lambda status: jubilant.all_active(status, *apps)


def any_error(*apps: str) -> StatusPredicate:
    """Return a predicate that checks if any given app is in error."""
    return lambda status: jubilant.any_error(status, *apps)


@contextmanager
def ldap_connection(
    uri: str, bind_dn: str, bind_password: str
) -> Generator[ldap.ldapobject.LDAPObject, None, None]:
    conn = ldap.initialize(uri)
    try:
        conn.simple_bind_s(bind_dn, bind_password)
        yield conn
    finally:
        conn.unbind_s()


def get_integration_data(
    juju: jubilant.Juju, app_name: str, integration_name: str, unit_num: int = 0
) -> Optional[jubilant.unittypes.RelationData]:
    unit_info = juju.show_unit(f"{app_name}/{unit_num}")
    return next(
        (rel for rel in unit_info.relation_info if rel.endpoint == integration_name),
        None,
    )


def get_app_integration_data(
    juju: jubilant.Juju,
    app_name: str,
    integration_name: str,
    unit_num: int = 0,
) -> Optional[dict]:
    data = get_integration_data(juju, app_name, integration_name, unit_num)
    if not data:
        return None
    if juju.version().major >= 4:
        remote_unit = next(
            (u for u in data.related_units if not u.startswith(f"{app_name}/")),
            None,
        )
        if not remote_unit:
            return None
        remote_info = juju.show_unit(remote_unit)
        rel = next(
            (r for r in remote_info.relation_info if r.relation_id == data.relation_id),
            None,
        )
        return rel.app_data if rel else None
    return data.app_data


@pytest.fixture
def app_integration_data(juju: jubilant.Juju) -> Callable:
    return functools.partial(get_app_integration_data, juju)


@pytest.fixture
def ingress_per_unit_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return app_integration_data(GLAUTH_APP, "ingress")


@pytest.fixture
def ingress_url(ingress_per_unit_integration_data: Optional[dict]) -> Optional[str]:
    if not ingress_per_unit_integration_data:
        return None

    ingress = ingress_per_unit_integration_data["ingress"]
    matched = INGRESS_URL_REGEX.search(ingress)
    assert matched is not None, "ingress url not found in ingress per unit integration data"

    return matched.group("ingress_url")


@pytest.fixture
def ldap_uri(ingress_url: Optional[str]) -> Optional[str]:
    return f"ldap://{ingress_url}" if ingress_url else None


@pytest.fixture
def database_integration_data(juju: jubilant.Juju, app_integration_data: Callable) -> dict:
    database_integration_data = app_integration_data(GLAUTH_APP, "pg-database") or {}
    secret_uri = database_integration_data["secret-user"]
    secret_content = juju.show_secret(secret_uri, reveal=True).content
    return {**database_integration_data, **secret_content}


@pytest.fixture(scope="module")
def run_action(juju: jubilant.Juju) -> Callable:
    def _run_action(application_name: str, action_name: str, **params: Any) -> dict[str, str]:
        action = juju.run(f"{application_name}/0", action_name, params=params)
        return action.results

    return _run_action


@pytest.fixture(scope="session")
def local_charm() -> Path:
    # in GitHub CI, charms are built with charmcraftcache and uploaded to $CHARM_PATH
    charm: str | Path | None = os.getenv("CHARM_PATH")
    if not charm:
        subprocess.run(["charmcraft", "pack"], check=True)
        if not (charms := list(Path(".").glob(f"{GLAUTH_UTILS_APP}*.charm"))):
            raise RuntimeError("Charm not found and build failed")
        charm = max(charms, key=lambda p: p.stat().st_mtime).absolute()
    return Path(charm)


def scp_ldif_file(juju: jubilant.Juju, source: str) -> None:
    juju.scp(source, f"{GLAUTH_UTILS_APP}/0:/var/tmp")


def apply_ldif(juju: jubilant.Juju, run_action: Callable, ldif_file: str) -> None:
    target_path = f"/var/tmp/{ldif_file}"
    scp_ldif_file(juju, f"./tests/integration/ldif/{ldif_file}")
    run_action(GLAUTH_UTILS_APP, "apply-ldif", path=target_path)


@pytest.fixture
def apply_add_ldif(juju: jubilant.Juju, run_action: Callable) -> None:
    apply_ldif(juju, run_action, "add.ldif")


@pytest.fixture
def apply_modify_ldif(juju: jubilant.Juju, run_action: Callable) -> None:
    apply_ldif(juju, run_action, "modify.ldif")


@pytest.fixture
def apply_rename_ldif(juju: jubilant.Juju, run_action: Callable) -> None:
    apply_ldif(juju, run_action, "rename.ldif")


@pytest.fixture
def apply_move_ldif(juju: jubilant.Juju, run_action: Callable) -> None:
    apply_ldif(juju, run_action, "move.ldif")


@pytest.fixture
def apply_attach_ldif(juju: jubilant.Juju, run_action: Callable) -> None:
    apply_ldif(juju, run_action, "attach.ldif")


@pytest.fixture
def apply_delete_ldif(juju: jubilant.Juju, run_action: Callable) -> None:
    apply_ldif(juju, run_action, "delete.ldif")


def unit_address(juju: jubilant.Juju, *, app_name: str, unit_num: int = 0) -> str:
    status = juju.status()
    return status.apps[app_name].units[f"{app_name}/{unit_num}"].address


@pytest.fixture
def database_address(juju: jubilant.Juju) -> str:
    return unit_address(juju, app_name=DB_APP)


@pytest.fixture
def initialize_database(database_integration_data: dict, database_address: str) -> None:
    assert database_integration_data, "database_integration_data should be ready"

    db_connection_params = {
        "dbname": database_integration_data["database"],
        "user": database_integration_data["username"],
        "password": database_integration_data["password"],
        "host": database_address,
        "port": 5432,
    }

    statements = Path("tests/integration/db.sql").read_text()
    with psycopg.Connection.connect(**db_connection_params) as conn:
        with conn.cursor() as cursor:
            cursor.execute(statements)
        conn.commit()
