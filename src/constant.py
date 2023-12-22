from collections.abc import KeysView
from enum import Enum
from typing import Final

USER_IDENTIFIER_ATTRIBUTE: Final[str] = "cn"

GROUP_IDENTIFIER_ATTRIBUTE: Final[str] = "ou"

LDIF_PARSER_IGNORED_ATTRIBUTES: Final[tuple[str, ...]] = ("objectClass",)

LDIF_SANITIZE_ATTRIBUTES: Final[tuple[str, ...]] = (
    "changetype",
    "add",
    "replace",
    "delete",
    "deleteoldrdn",
    "newrdn",
    "newsuperior",
    "objectClass",
)

LDIF_TO_USER_MODEL_MAPPINGS: Final[dict[str, str]] = {
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

LDIF_TO_GROUP_MODEL_MAPPINGS: Final[dict[str, str]] = {
    "ou": "name",
    "gidNumber": "gid_number",
    "memberUid": "member_uid",
}

LDIF_TO_INCLUDE_GROUP_MODEL_MAPPINGS: Final[dict[str, str]] = {
    "parentGroup": "parent_group",
    "childGroup": "child_group",
}

SUPPORTED_LDIF_ATTRIBUTES: Final[KeysView] = (
    LDIF_TO_USER_MODEL_MAPPINGS | LDIF_TO_GROUP_MODEL_MAPPINGS
).keys()

PASSWORD_ALGORITHM_REGISTRY: Final[dict[str, str]] = {
    "sha256": "passwordSha256",
    "bcrypt": "passwordBcrypt",
}


class OperationType(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"
    ATTACH = "attach"
    DETACH = "detach"
