# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "The Juju application name"
  value       = juju_application.glauth_utils.name
}

output "requires" {
  description = "The Juju integrations that the charm requires"
  value = {
    glauth-auxiliary = "glauth-auxiliary"
  }
}
