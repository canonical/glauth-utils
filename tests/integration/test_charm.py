#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
GLAUTH_UTILS_APP_NAME = METADATA["name"]


@pytest.mark.skip_if_deployed
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    charm_path = await ops_test.build_charm(".")
    await ops_test.model.deploy(
        str(charm_path),
        application_name=GLAUTH_UTILS_APP_NAME,
        trust=True,
        series="jammy",
    )

    await ops_test.model.wait_for_idle(
        apps=[GLAUTH_UTILS_APP_NAME],
        status="blocked",
        raise_on_blocked=False,
        timeout=1000,
    )
