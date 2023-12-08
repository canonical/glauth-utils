# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from dataclasses import asdict

from charm import AUXILIARY_INTEGRATION_NAME
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Harness

from lib.charms.glauth_utils.v0.glauth_auxiliary import AuxiliaryData

GLAUTH_APP_NAME = "glauth-k8s"
GLAUTH_UNIT_NAME = "/".join([GLAUTH_APP_NAME, "0"])


class TestStartEvent:
    def test_on_start_no_auxiliary_integration(self, harness: Harness) -> None:
        harness.charm.on.start.emit()
        assert isinstance(harness.model.unit.status, BlockedStatus)

    def test_on_start_no_auxiliary_integration_data(self, harness: Harness) -> None:
        integration_id = harness.add_relation(AUXILIARY_INTEGRATION_NAME, GLAUTH_APP_NAME)
        harness.add_relation_unit(integration_id, GLAUTH_UNIT_NAME)

        harness.charm.on.start.emit()
        assert isinstance(harness.model.unit.status, WaitingStatus)

    def test_on_start(self, harness: Harness) -> None:
        auxiliary_data = AuxiliaryData(
            database=GLAUTH_APP_NAME,
            endpoint="<ENDPOINT>",
            username="<USERNAME>",
            password="<PASSWORD>",
        )
        integration_id = harness.add_relation(AUXILIARY_INTEGRATION_NAME, GLAUTH_APP_NAME)
        harness.add_relation_unit(integration_id, GLAUTH_UNIT_NAME)
        harness.update_relation_data(
            integration_id,
            GLAUTH_APP_NAME,
            asdict(auxiliary_data),
        )

        harness.charm.on.start.emit()
        assert isinstance(harness.model.unit.status, ActiveStatus)
