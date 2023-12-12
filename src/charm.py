#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""A Juju Kubernetes charmed operator for GLAuth Utility Features."""

import logging
from pathlib import Path

from action import apply_ldif
from charms.glauth_utils.v0.glauth_auxiliary import AuxiliaryReadyEvent, AuxiliaryRequirer
from ops.charm import ActionEvent, CharmBase, StartEvent
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

        self.framework.observe(
            self.on.apply_ldif_action,
            self._on_apply_ldif_action,
        )

    def _on_start(self, event: StartEvent) -> None:
        self.unit.status = MaintenanceStatus("Configuring the glauth-utils charm.")

        if not (auxiliary_integrations := self.model.relations[AUXILIARY_INTEGRATION_NAME]):
            self.unit.status = BlockedStatus("Waiting for the required auxiliary integration.")
            return

        auxiliary_integration = auxiliary_integrations[0]
        if not auxiliary_integration.data.get(auxiliary_integration.app):
            self.unit.status = WaitingStatus("Waiting for the auxiliary data.")
            return

        self.unit.status = ActiveStatus()

    def _on_auxiliary_ready(self, event: AuxiliaryReadyEvent) -> None:
        self.unit.status = ActiveStatus()

    def _on_apply_ldif_action(self, event: ActionEvent) -> None:
        if not isinstance(self.unit.status, ActiveStatus):
            event.fail(f"The {self.app.name} is not ready yet.")
            return

        ldif_file = event.params.get("path")
        if not Path(ldif_file).is_file():
            event.fail(f"The LDIF file {ldif_file} does not exist.")
            return

        auxiliary_data = self.auxiliary_requirer.consume_auxiliary_relation_data()
        dsn = (
            f"postgresql+psycopg://"
            f"{auxiliary_data.username}:"
            f"{auxiliary_data.password}@"
            f"{auxiliary_data.endpoint}/"
            f"{auxiliary_data.database}"
        )

        event.log("Applying LDIF file...")
        try:
            apply_ldif(ldif_file, dsn)
        except Exception:
            event.fail(f"Failed to apply the LDIF file: {ldif_file}.")
            return
        event.log(f"Successfully applied LDIF file: {ldif_file}.")


if __name__ == "__main__":
    main(GLAuthUtilsCharm)
