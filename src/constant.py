from enum import Enum

USER_IDENTIFIER_ATTRIBUTE = "cn"

GROUP_IDENTIFIER_ATTRIBUTE = "ou"

LDIF_PARSER_IGNORED_ATTRIBUTES = ("objectClass",)

LDIF_SANITIZE_ATTRIBUTES = (
    "changetype",
    "add",
    "replace",
    "delete",
    "deleteoldrdn",
    "newrdn",
    "newsuperior",
    "objectClass",
)

LDIF_TO_USER_MODEL_MAPPINGS = {
    "cn": "name",
    "uidNumber": "uid_number",
    "gidNumber": "gid_number",
    "mail": "email",
    "sn": "surname",
    "givenName": "given_name",
    "passwordSha256": "password_sha256",
    "passwordBcrypt": "password_bcrypt",
    "loginShell": "login_shell",
    "homeDirectory": "home_directory",
    "accountStatus": "account_status",
    "yubiKeyId": "yubi_key",
    "sshPublicKey": "ssh_keys",
}

LDIF_TO_GROUP_MODEL_MAPPINGS = {
    "ou": "name",
    "gidNumber": "gid_number",
}

SUPPORTED_LDIF_ATTRIBUTES = (LDIF_TO_USER_MODEL_MAPPINGS | LDIF_TO_GROUP_MODEL_MAPPINGS).keys()

PASSWORD_ALGORITHM_REGISTRY = {
    "sha256": "passwordSha256",
    "bcrypt": "passwordBcrypt",
}


class OperationType(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"
