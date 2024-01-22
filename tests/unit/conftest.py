# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Callable
from unittest.mock import MagicMock

import pytest
from charm import GLAuthUtilsCharm
from constants import (
    AUXILIARY_INTEGRATION_NAME,
    GROUP_IDENTIFIER_ATTRIBUTE,
    USER_IDENTIFIER_ATTRIBUTE,
)
from database import Group, User
from ops.testing import Harness
from parser import Record, stringify_processor
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


@pytest.fixture
def record() -> Record:
    return Record()


@pytest.fixture(scope="session")
def user_dn() -> str:
    return "cn=hackers,ou=superheros,dc=glauth,dc=com"


@pytest.fixture
def user_record() -> Record:
    return Record(
        identifier=USER_IDENTIFIER_ATTRIBUTE,
        model=User,
    )


@pytest.fixture
def raw_user_entry() -> dict:
    return {
        "cn": [b"hackers"],
        "uidNumber": [b"5001"],
        "gidNumber": [b"5501"],
        "mail": [b"hackers@glauth.com"],
        "sn": [b"hackers"],
    }


@pytest.fixture(scope="session")
def group_dn() -> str:
    return "ou=superheros,dc=glauth,dc=com"


@pytest.fixture
def group_record() -> Record:
    return Record(
        identifier=GROUP_IDENTIFIER_ATTRIBUTE,
        model=Group,
    )


@pytest.fixture
def raw_group_entry() -> dict:
    return {
        "ou": [b"superheros"],
        "gidNumber": [b"5501"],
    }


@pytest.fixture
def make_stringify_entry() -> Callable:
    def _stringify(dn, entry, record):
        stringify_processor(dn, entry, record)

    return _stringify


@pytest.fixture
def stringify_user_entry(
    make_stringify_entry: Callable,
    user_dn,
    raw_user_entry,
    user_record,
):
    make_stringify_entry(user_dn, raw_user_entry, user_record)
    return raw_user_entry


@pytest.fixture
def stringify_group_entry(
    make_stringify_entry: Callable,
    group_dn,
    raw_group_entry,
    group_record,
):
    make_stringify_entry(group_dn, raw_group_entry, group_record)
    return raw_group_entry
