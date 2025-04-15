# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import functools
import os
import re
from base64 import b64decode
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional

import aiofiles
import ldap
import psycopg
import pytest_asyncio
import yaml
from pytest_operator.plugin import OpsTest

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


@contextmanager
def ldap_connection(uri: str, bind_dn: str, bind_password: str) -> ldap.ldapobject.LDAPObject:
    conn = ldap.initialize(uri)
    try:
        conn.simple_bind_s(bind_dn, bind_password)
        yield conn
    finally:
        conn.unbind_s()


async def get_unit_data(ops_test: OpsTest, unit_name: str) -> dict:
    show_unit_cmd = f"show-unit {unit_name}".split()
    _, stdout, _ = await ops_test.juju(*show_unit_cmd)
    cmd_output = yaml.safe_load(stdout)
    return cmd_output[unit_name]


async def get_integration_data(
    ops_test: OpsTest, app_name: str, integration_name: str, unit_num: int = 0
) -> Optional[dict]:
    data = await get_unit_data(ops_test, f"{app_name}/{unit_num}")
    return next(
        (
            integration
            for integration in data["relation-info"]
            if integration["endpoint"] == integration_name
        ),
        None,
    )


async def get_app_integration_data(
    ops_test: OpsTest,
    app_name: str,
    integration_name: str,
    unit_num: int = 0,
) -> Optional[dict]:
    data = await get_integration_data(ops_test, app_name, integration_name, unit_num)
    return data["application-data"] if data else None


@pytest_asyncio.fixture
async def app_integration_data(ops_test: OpsTest) -> Callable:
    return functools.partial(get_app_integration_data, ops_test)


@pytest_asyncio.fixture
async def ingress_per_unit_integration_data(app_integration_data: Callable) -> Optional[dict]:
    return await app_integration_data(GLAUTH_APP, "ingress")


@pytest_asyncio.fixture
async def ingress_url(ingress_per_unit_integration_data: Optional[dict]) -> Optional[str]:
    if not ingress_per_unit_integration_data:
        return None

    ingress = ingress_per_unit_integration_data["ingress"]
    matched = INGRESS_URL_REGEX.search(ingress)
    assert matched is not None, "ingress url not found in ingress per unit integration data"

    return matched.group("ingress_url")


@pytest_asyncio.fixture
async def ldap_uri(ingress_url: Optional[str]) -> Optional[str]:
    return f"ldap://{ingress_url}" if ingress_url else None


@pytest_asyncio.fixture
async def database_integration_data(ops_test: OpsTest, app_integration_data: Callable) -> dict:
    database_integration_data = await app_integration_data(GLAUTH_APP, "pg-database") or {}

    db_credentials = await ops_test.model.list_secrets(
        filter={"uri": database_integration_data["secret-user"]},
        show_secrets=True,
    )
    db_credential = next(iter(db_credentials), None)
    assert db_credential
    decoded_db_credentials = {
        field: b64decode(db_credential.value.data[field]).decode("utf-8")
        for field in ("username", "password")
    }

    return {**database_integration_data, **decoded_db_credentials}


@pytest_asyncio.fixture(scope="module")
def run_action(ops_test: OpsTest) -> Callable:
    async def _run_action(
        application_name: str, action_name: str, **params: Any
    ) -> dict[str, str]:
        app = ops_test.model.applications[application_name]
        action = await app.units[0].run_action(action_name, **params)
        await action.wait()
        return action.results

    return _run_action


@pytest_asyncio.fixture(scope="module")
async def local_charm(ops_test: OpsTest) -> Path:
    # in GitHub CI, charms are built with charmcraftcache and uploaded to $CHARM_PATH
    charm = os.getenv("CHARM_PATH")
    if not charm:
        # fall back to build locally - required when run outside of GitHub CI
        charm = await ops_test.build_charm(".")
    return charm


async def scp_ldif_file(ops_test: OpsTest, source: str) -> None:
    app = ops_test.model.applications[GLAUTH_UTILS_APP]
    scp_cmd = f"scp {source} {app.units[0].name}:/var/tmp".split()
    await ops_test.juju(*scp_cmd)


async def apply_ldif(ops_test: OpsTest, run_action: Callable, ldif_file: str) -> None:
    target_path = f"/var/tmp/{ldif_file}"
    await scp_ldif_file(ops_test, f"./tests/integration/ldif/{ldif_file}")
    await run_action(GLAUTH_UTILS_APP, "apply-ldif", path=target_path)


@pytest_asyncio.fixture
async def apply_add_ldif(ops_test: OpsTest, run_action: Callable) -> None:
    await apply_ldif(ops_test, run_action, "add.ldif")


@pytest_asyncio.fixture
async def apply_modify_ldif(ops_test: OpsTest, run_action: Callable) -> None:
    await apply_ldif(ops_test, run_action, "modify.ldif")


@pytest_asyncio.fixture
async def apply_rename_ldif(ops_test: OpsTest, run_action: Callable) -> None:
    await apply_ldif(ops_test, run_action, "rename.ldif")


@pytest_asyncio.fixture
async def apply_move_ldif(ops_test: OpsTest, run_action: Callable) -> None:
    await apply_ldif(ops_test, run_action, "move.ldif")


@pytest_asyncio.fixture
async def apply_attach_ldif(ops_test: OpsTest, run_action: Callable) -> None:
    await apply_ldif(ops_test, run_action, "attach.ldif")


@pytest_asyncio.fixture
async def apply_delete_ldif(ops_test: OpsTest, run_action: Callable) -> None:
    await apply_ldif(ops_test, run_action, "delete.ldif")


async def unit_address(ops_test: OpsTest, *, app_name: str, unit_num: int = 0) -> str:
    status = await ops_test.model.get_status()
    return status["applications"][app_name]["units"][f"{app_name}/{unit_num}"]["address"]


@pytest_asyncio.fixture
async def database_address(ops_test: OpsTest) -> str:
    return await unit_address(ops_test, app_name=DB_APP)


@pytest_asyncio.fixture
async def initialize_database(database_integration_data: dict, database_address: str) -> None:
    assert database_integration_data, "database_integration_data should be ready"

    db_connection_params = {
        "dbname": database_integration_data["database"],
        "user": database_integration_data["username"],
        "password": database_integration_data["password"],
        "host": database_address,
        "port": 5432,
    }

    async with await psycopg.AsyncConnection.connect(**db_connection_params) as conn:
        async with conn.cursor() as cursor:
            async with aiofiles.open("tests/integration/db.sql", "rb") as f:
                statements = await f.read()

            await cursor.execute(statements)
            await conn.commit()
