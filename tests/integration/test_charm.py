#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Optional

import ldap
import pytest
from conftest import (
    BASE_DN,
    BIND_DN,
    BIND_PASSWORD,
    CERTIFICATE_PROVIDER_APP,
    DB_APP,
    GLAUTH_APP,
    GLAUTH_UTILS_APP,
    INGRESS_APP,
    TRAEFIK_CHARM,
    ldap_connection,
)
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_deploy_dependencies(ops_test: OpsTest) -> None:
    await ops_test.model.deploy(
        CERTIFICATE_PROVIDER_APP,
        channel="latest/stable",
        trust=True,
    )
    await ops_test.model.deploy(
        DB_APP,
        channel="14/stable",
        trust=True,
    )
    (
        await ops_test.model.deploy(
            TRAEFIK_CHARM,
            application_name=INGRESS_APP,
            channel="latest/edge",
            trust=True,
        ),
    )
    await ops_test.model.wait_for_idle(
        apps=[CERTIFICATE_PROVIDER_APP, DB_APP, INGRESS_APP],
        status="active",
        raise_on_blocked=False,
        timeout=5 * 60,
    )
    await ops_test.model.deploy(
        GLAUTH_APP,
        channel="latest/edge",
        trust=True,
    )
    await ops_test.model.integrate(GLAUTH_APP, DB_APP)
    await ops_test.model.integrate(GLAUTH_APP, CERTIFICATE_PROVIDER_APP)
    await ops_test.model.integrate(f"{GLAUTH_APP}:ingress", f"{INGRESS_APP}:ingress-per-unit")

    await ops_test.model.wait_for_idle(
        apps=[CERTIFICATE_PROVIDER_APP, DB_APP, GLAUTH_APP, INGRESS_APP],
        status="active",
        raise_on_error=False,
        raise_on_blocked=False,
        timeout=5 * 60,
    )


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, initialize_database: None) -> None:
    charm_path = await ops_test.build_charm(".")
    await ops_test.model.deploy(
        str(charm_path),
        application_name=GLAUTH_UTILS_APP,
        trust=True,
        series="jammy",
    )
    await ops_test.model.integrate(GLAUTH_UTILS_APP, GLAUTH_APP)

    await ops_test.model.wait_for_idle(
        apps=[GLAUTH_UTILS_APP, GLAUTH_APP],
        status="active",
        raise_on_blocked=True,
        timeout=5 * 60,
    )


async def test_added_entries(
    ldap_uri: Optional[str],
    apply_add_ldif: None,
) -> None:
    # Search the group "superheros"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(&(objectClass=posixGroup)(ou=superheros))",
        )

    assert res[0], "Can't find group 'superheros'"
    dn, _ = res[0]
    assert dn == f"ou=superheros,ou=users,{BASE_DN}"

    # Search the subgroup "caped"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(&(objectClass=posixGroup)(ou=caped))",
        )

    assert res[0], "Can't find group 'caped'"
    dn, _ = res[0]
    assert dn == f"ou=caped,ou=users,{BASE_DN}"

    # Search the user "johndoe"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(cn=johndoe)",
        )

    assert res[0], "Can't find user 'johndoe'"
    dn, _ = res[0]
    assert dn == f"cn=johndoe,ou=superheros,ou=users,{BASE_DN}"


async def test_modify_entries(
    ldap_uri: Optional[str],
    apply_modify_ldif: None,
) -> None:
    # Search the group "svcaccts"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(&(objectClass=posixGroup)(ou=svcaccts))",
        )

    assert res[0], "Can't find group 'svcaccts'"
    dn, attrs = res[0]
    assert dn == f"ou=svcaccts,ou=users,{BASE_DN}"
    assert attrs["gidNumber"][0] == b"5514"

    # Search the user "modify"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(cn=modify)",
        )

    assert res[0], "Can't find user 'modify'"
    dn, attrs = res[0]
    assert dn == f"cn=modify,ou=smoker,ou=users,{BASE_DN}"
    assert attrs["sn"][0] == b"wick"
    assert attrs["loginShell"][0] == b"/bin/bash"
    assert "email" not in attrs


async def test_rename_entries(
    ldap_uri: Optional[str],
    apply_rename_ldif: None,
) -> None:
    # Search the renamed user "rename"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(cn=new_rename)",
        )

    assert res[0], "Can't find user 'new_rename'"
    dn, _ = res[0]
    assert dn == f"cn=new_rename,ou=rename,ou=users,{BASE_DN}"


async def test_move_entries(
    ldap_uri: Optional[str],
    apply_move_ldif: None,
) -> None:
    # Search the moved group "sub"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(&(objectClass=posixGroup)(ou=sub))",
        )

    assert res[0], "Can't find group 'sub'"
    dn, _ = res[0]
    assert dn == f"ou=sub,ou=users,{BASE_DN}"

    # Search the moved user "move"
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="cn=move",
        )

    assert res[0], "Can't find user 'move'"
    dn, _ = res[0]
    assert dn == f"cn=move,ou=sub,ou=users,{BASE_DN}"


async def test_attach_entries(
    ldap_uri: Optional[str],
    apply_attach_ldif: None,
) -> None:
    # Search the user "attach" (attached to group "secondary")
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="cn=attach",
        )

    assert res[0], "Can't find user 'attach'"
    dn, attrs = res[0]
    assert dn == f"cn=attach,ou=primary,ou=users,{BASE_DN}"
    assert attrs["memberOf"] == [
        b"ou=primary,ou=groups,dc=glauth,dc=com",
        b"ou=secondary,ou=groups,dc=glauth,dc=com",
    ]

    # Search the user "detach" (detached from group "secondary")
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="cn=detach",
        )

    assert res[0], "Can't find user 'detach'"
    dn, attrs = res[0]
    assert dn == f"cn=detach,ou=primary,ou=users,{BASE_DN}"
    assert attrs["memberOf"] == [b"ou=primary,ou=groups,dc=glauth,dc=com"]


async def test_delete_entries(
    ldap_uri: Optional[str],
    apply_delete_ldif: None,
) -> None:
    # Search the deleted user
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="cn=delete",
        )

    assert not res, "The user 'delete' should be deleted"

    # Search the deleted group
    with ldap_connection(uri=ldap_uri, bind_dn=BIND_DN, bind_password=BIND_PASSWORD) as conn:
        res = conn.search_s(
            base=BASE_DN,
            scope=ldap.SCOPE_SUBTREE,
            filterstr="(&(objectClass=posixGroup)(ou=deleted))",
        )

    assert not res, "The group 'delete' should be deleted"
