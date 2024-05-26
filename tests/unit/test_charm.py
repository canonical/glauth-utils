# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

import pytest
from conftest import LDIF_FILE_PATH
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import ActionFailed, Harness

from exceptions import InvalidAttributeValueError, InvalidDistinguishedNameError
from lib.charms.glauth_utils.v0.glauth_auxiliary import AuxiliaryData

GLAUTH_APP_NAME = "glauth-k8s"
GLAUTH_UNIT_NAME = "/".join([GLAUTH_APP_NAME, "0"])


class TestStartEvent:
    def test_on_start_no_auxiliary_integration(self, harness: Harness) -> None:
        harness.charm.on.start.emit()
        assert isinstance(harness.model.unit.status, BlockedStatus)

    def test_on_start_no_auxiliary_integration_data(
        self, harness: Harness, auxiliary_integration: int
    ) -> None:
        harness.charm.on.start.emit()
        assert isinstance(harness.model.unit.status, WaitingStatus)

    def test_on_start(
        self, harness: Harness, auxiliary_integration: int, auxiliary_data_ready: AuxiliaryData
    ) -> None:
        harness.charm.on.start.emit()
        assert isinstance(harness.model.unit.status, ActiveStatus)


class TestAuxiliaryReadyEvent:
    def test_on_auxiliary_ready(
        self, harness: Harness, auxiliary_integration: int, auxiliary_data_ready: AuxiliaryData
    ) -> None:
        assert isinstance(harness.model.unit.status, ActiveStatus)


class TestAuxiliaryUnavailableEvent:
    def test_on_auxiliary_unavailable(
        self, harness: Harness, auxiliary_integration: int, auxiliary_data_ready: AuxiliaryData
    ) -> None:
        harness.remove_relation(auxiliary_integration)
        assert isinstance(harness.model.unit.status, BlockedStatus)


class TestApplyLdifAction:
    def test_charm_not_ready(self, harness: Harness) -> None:
        with pytest.raises(ActionFailed) as exc:
            harness.run_action("apply-ldif", {"path": LDIF_FILE_PATH})

        assert f"The {harness.charm.app.name} is not ready yet." == exc.value.message

    def test_ldif_not_exists(self, harness: Harness) -> None:
        harness.model.unit.status = ActiveStatus()
        with pytest.raises(ActionFailed) as exc:
            harness.run_action("apply-ldif", {"path": LDIF_FILE_PATH})

        assert f"The LDIF file {LDIF_FILE_PATH} does not exist." == exc.value.message

    def test_auxiliary_data_not_ready(self, harness: Harness, ldif_file_mock: MagicMock) -> None:
        harness.model.unit.status = ActiveStatus()
        with pytest.raises(ActionFailed) as exc:
            harness.run_action("apply-ldif", {"path": LDIF_FILE_PATH})

        assert "The auxiliary data is not ready yet." == exc.value.message

    @patch("charm.apply_ldif", side_effect=InvalidAttributeValueError)
    def test_with_invalid_ldif_attribute(
        self,
        mocked_apply_ldif: MagicMock,
        harness: Harness,
        auxiliary_integration: int,
        auxiliary_data_ready: AuxiliaryData,
        ldif_file_mock: MagicMock,
    ) -> None:
        harness.model.unit.status = ActiveStatus()

        with pytest.raises(ActionFailed) as exc:
            harness.run_action("apply-ldif", {"path": LDIF_FILE_PATH})

        assert any(
            log.find("Failed to parse the LDIF file.") > -1 for log in exc.value.output.logs
        )

    @patch("charm.apply_ldif", side_effect=InvalidDistinguishedNameError)
    def test_with_invalid_ldif_distinguished_name(
        self,
        mocked_apply_ldif: MagicMock,
        harness: Harness,
        auxiliary_integration: int,
        auxiliary_data_ready: AuxiliaryData,
        ldif_file_mock: MagicMock,
    ) -> None:
        harness.model.unit.status = ActiveStatus()

        with pytest.raises(ActionFailed) as exc:
            harness.run_action("apply-ldif", {"path": LDIF_FILE_PATH})

        assert any(
            log.find("Failed to parse the LDIF file.") > -1 for log in exc.value.output.logs
        )

    @patch("charm.apply_ldif", side_effect=Exception)
    def test_with_unknown_error(
        self,
        mocked_apply_ldif: MagicMock,
        harness: Harness,
        auxiliary_integration: int,
        auxiliary_data_ready: AuxiliaryData,
        ldif_file_mock: MagicMock,
    ) -> None:
        harness.model.unit.status = ActiveStatus()

        with pytest.raises(ActionFailed) as exc:
            harness.run_action("apply-ldif", {"path": LDIF_FILE_PATH})

        assert any(
            log.find("Failed to apply the LDIF file.") > -1 for log in exc.value.output.logs
        )

    @patch("charm.apply_ldif")
    def test_run_action(
        self,
        mocked_apply_ldif: MagicMock,
        harness: Harness,
        auxiliary_integration: int,
        auxiliary_data_ready: AuxiliaryData,
        ldif_file_mock: MagicMock,
    ) -> None:
        harness.model.unit.status = ActiveStatus()

        output = harness.run_action("apply-ldif", {"path": LDIF_FILE_PATH})
        assert any(log.find("Successfully applied the LDIF file.") > -1 for log in output.logs)
