#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
CERTIFICATE_PROVIDER_APP = "self-signed-certificates"
GLAUTH_UTILS_APP = METADATA["name"]
GLAUTH_APP = "glauth-k8s"
DB_APP = "postgresql-k8s"


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    await ops_test.model.deploy(
        CERTIFICATE_PROVIDER_APP,
        channel="stable",
        trust=True,
    )
    await ops_test.model.deploy(
        DB_APP,
        channel="14/stable",
        trust=True,
    )
    await ops_test.model.wait_for_idle(
        apps=[CERTIFICATE_PROVIDER_APP, DB_APP],
        status="active",
        raise_on_blocked=True,
        timeout=1000,
    )

    await ops_test.model.deploy(
        GLAUTH_APP,
        channel="edge",
        trust=True,
    )
    await ops_test.model.integrate(GLAUTH_APP, DB_APP)
    await ops_test.model.integrate(GLAUTH_APP, CERTIFICATE_PROVIDER_APP)

    await ops_test.model.wait_for_idle(
        apps=[CERTIFICATE_PROVIDER_APP, DB_APP, GLAUTH_APP],
        status="active",
        raise_on_error=False,
        raise_on_blocked=False,
        timeout=1000,
    )

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
        timeout=1000,
    )
