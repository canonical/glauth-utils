# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock

import pytest
from charm import GLAuthUtilsCharm
from constants import AUXILIARY_INTEGRATION_NAME
from ops.testing import Harness
from pytest_mock import MockerFixture

from lib.charms.glauth_utils.v0.glauth_auxiliary import AuxiliaryData

LDIF_FILE_PATH = "foo"
REMOTE_APP = "glauth-k8s"


@pytest.fixture
def harness() -> Harness:
    harness = Harness(GLAuthUtilsCharm)
    harness.set_model_name("unit-test")
    harness.set_leader(True)

    harness.begin()
    yield harness
    harness.cleanup()


@pytest.fixture
def auxiliary_integration(harness: Harness) -> int:
    integration_id = harness.add_relation(AUXILIARY_INTEGRATION_NAME, REMOTE_APP)
    harness.add_relation_unit(integration_id, f"{REMOTE_APP}/0")
    return integration_id


@pytest.fixture
def auxiliary_data_ready(harness: Harness, auxiliary_integration: int) -> AuxiliaryData:
    auxiliary_data = AuxiliaryData(
        database=REMOTE_APP,
        endpoint="<ENDPOINT>",
        username="<USERNAME>",
        password="<PASSWORD>",
    )
    harness.update_relation_data(
        auxiliary_integration,
        REMOTE_APP,
        auxiliary_data.model_dump(),
    )

    return auxiliary_data


@pytest.fixture
def ldif_file_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("pathlib.Path.is_file", return_value=True)
