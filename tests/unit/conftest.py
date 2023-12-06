# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from charm import GLAuthUtilsCharm
from ops.testing import Harness


@pytest.fixture()
def harness() -> Harness:
    harness = Harness(GLAuthUtilsCharm)
    harness.set_model_name("unit-test")
    harness.set_leader(True)

    harness.begin()
    yield harness
    harness.cleanup()
