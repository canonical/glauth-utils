/**
 * # Terraform Module for GLAuth Utils Operator
 *
 * This is a Terraform module facilitating the deployment of the glauth-utils
 * charm using the Juju Terraform provider.
 */

resource "juju_application" "glauth_utils" {
  name        = var.app_name
  model       = var.model_name
  trust       = true
  config      = var.config
  constraints = var.constraints
  units       = var.units

  charm {
    name     = "glauth-utils"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }
}
