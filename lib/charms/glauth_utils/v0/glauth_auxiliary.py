# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""# Juju Charm Library for the `glauth_auxiliary` Juju Interface.

This juju charm library contains the Provider and Requirer classes for handling
the `glauth_auxiliary` interface.

## Requirer Charm

The requirer charm is expected to:

- Listen to the custom juju event `AuxiliaryReadyEvent` to consume the
auxiliary data from the integration

```python

from charms.glauth_utils.v0.glauth_auxiliary import (
    AuxiliaryRequirer,
    AuxiliaryReadyEvent,
)

class RequirerCharm(CharmBase):
    # Auxiliary requirer charm that integrates with an auxiliary provider charm.

    def __init__(self, *args):
        super().__init__(*args)

        self.auxiliary_requirer = AuxiliaryRequirer(self)
        self.framework.observe(
            self.auxiliary_requirer.on.auxiliary_ready,
            self._on_auxiliary_ready,
        )

    def _on_auxiliary_ready(self, event: AuxiliaryReadyEvent) -> None:
        # Consume the auxiliary data
        auxiliary_data = self.auxiliary_requirer.consume_auxiliary_relation_data(
            event.relation.id,
        )
```

As shown above, the library offers custom juju event to handle the specific
situation, which are listed below:

- auxiliary_ready: event emitted when the auxiliary data is ready for
requirer charm to use.

Additionally, the requirer charmed operator needs to declare the `auxiliary`
interface in the `metadata.yaml`:

```yaml
requires:
  glauth-auxiliary:
    interface: glauth_auxiliary
    limit: 1
```

## Provider Charm

The provider charm is expected to:

- Listen to the custom juju event `AuxiliaryRequestedEvent` to provide the
auxiliary data in the integration

```python

from charms.glauth_utils.v0.glauth_auxiliary import (
    AuxiliaryProvider,
    AuxiliaryRequestedEvent,
)

class ProviderCharm(CharmBase):
    # Auxiliary provider charm.

    def __init__(self, *args):
        super().__init__(*args)

        self.auxiliary_provider = AuxiliaryProvider(self)
        self.framework.observe(
            self.auxiliary_provider.on.auxiliary_requested,
            self._on_auxiliary_requested,
        )

    def _on_auxiliary_requested(self, event: AuxiliaryRequestedEvent) -> None:
        # Prepare the auxiliary data
        auxiliary_data = ...

        # Update the integration data
        self.auxiliary_provider.update_relation_app_data(
            relation.id,
            auxiliary_data,
        )
```

As shown above, the library offers custom juju event to handle the specific
situation, which are listed below:

-  auxiliary_requested: event emitted when the requirer charm integrates with
the provider charm

"""

from dataclasses import asdict, dataclass
from functools import wraps
from typing import Any, Callable, Optional, Union

from dacite import from_dict
from ops.charm import (
    CharmBase,
    RelationChangedEvent,
    RelationCreatedEvent,
    RelationEvent,
)
from ops.framework import EventSource, Object, ObjectEvents

# The unique Charmhub library identifier, never change it
LIBID = "8c3a907cf23345ea8be7fccfe15b2cf7"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

PYDEPS = ["dacite~=1.8.0"]

DEFAULT_RELATION_NAME = "glauth-auxiliary"


def leader_unit(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(
        obj: Union["AuxiliaryProvider", "AuxiliaryRequirer"],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[Any]:
        if not obj.unit.is_leader():
            return None

        return func(obj, *args, **kwargs)

    return wrapper


@dataclass(frozen=True)
class AuxiliaryData:
    database: str
    endpoint: str
    username: str
    password: str


class AuxiliaryRequestedEvent(RelationEvent):
    """An event emitted when the auxiliary integration is built."""


class AuxiliaryReadyEvent(RelationEvent):
    """An event emitted when the auxiliary data is ready."""


class AuxiliaryProviderEvents(ObjectEvents):
    auxiliary_requested = EventSource(AuxiliaryRequestedEvent)


class AuxiliaryRequirerEvents(ObjectEvents):
    auxiliary_ready = EventSource(AuxiliaryReadyEvent)


class AuxiliaryProvider(Object):
    on = AuxiliaryProviderEvents()

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = DEFAULT_RELATION_NAME,
    ) -> None:
        super().__init__(charm, relation_name)

        self.charm = charm
        self.app = charm.app
        self.unit = charm.unit
        self._relation_name = relation_name

        self.framework.observe(
            self.charm.on[self._relation_name].relation_created,
            self._on_relation_created,
        )

    @leader_unit
    def _on_relation_created(self, event: RelationCreatedEvent) -> None:
        """Handle the event emitted when an auxiliary integration is created."""
        self.on.auxiliary_requested.emit(event.relation)

    @leader_unit
    def update_relation_app_data(self, /, relation_id: int, data: AuxiliaryData) -> None:
        """An API for the provider charm to provide the auxiliary data."""
        if not (relation := self.charm.model.get_relation(self._relation_name, relation_id)):
            return

        relation.data[self.app].update(asdict(data))


class AuxiliaryRequirer(Object):
    on = AuxiliaryRequirerEvents()

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = DEFAULT_RELATION_NAME,
    ) -> None:
        super().__init__(charm, relation_name)

        self.charm = charm
        self.app = charm.app
        self.unit = charm.unit
        self._relation_name = relation_name

        self.framework.observe(
            self.charm.on[self._relation_name].relation_changed,
            self._on_relation_changed,
        )

    @leader_unit
    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Handle the event emitted when auxiliary data is ready."""
        if not event.relation.data.get(event.relation.app):
            return

        self.on.auxiliary_ready.emit(event.relation)

    def consume_auxiliary_relation_data(
        self,
        /,
        relation_id: Optional[int] = None,
    ) -> Optional[AuxiliaryData]:
        """An API for the requirer charm to consume the auxiliary data."""
        if not (relation := self.charm.model.get_relation(self._relation_name, relation_id)):
            return None

        if not (auxiliary_data := relation.data.get(relation.app)):
            return None

        return (
            from_dict(
                data_class=AuxiliaryData,
                data=auxiliary_data,
            )
            if auxiliary_data
            else None
        )
