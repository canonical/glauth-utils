#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""A Juju Kubernetes charmed operator for GLAuth Utility Features."""

import logging

from charms.glauth_utils.v0.glauth_auxiliary import AuxiliaryReadyEvent, AuxiliaryRequirer
from ops.charm import CharmBase, StartEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

logger = logging.getLogger(__name__)

AUXILIARY_INTEGRATION_NAME = "glauth-auxiliary"


class GLAuthUtilsCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)

        self.framework.observe(self.on.start, self._on_start)

        self.auxiliary_requirer = AuxiliaryRequirer(self)
        self.framework.observe(
            self.auxiliary_requirer.on.auxiliary_ready,
            self._on_auxiliary_ready,
        )

    def _on_start(self, event: StartEvent) -> None:
        self.unit.status = MaintenanceStatus("Configuring the utils charm.")

        if not self.model.relations[AUXILIARY_INTEGRATION_NAME]:
            self.unit.status = BlockedStatus("Waiting for the required auxiliary integration.")
            return

        self.unit.status = ActiveStatus()

    def _on_auxiliary_ready(self, event: AuxiliaryReadyEvent) -> None:
        auxiliary_data = self.auxiliary_requirer.consume_auxiliary_relation_data(
            relation_id=event.relation.id
        )

        if not auxiliary_data:
            self.unit.status = WaitingStatus("Waiting for the auxiliary data.")
            return

        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(GLAuthUtilsCharm)
