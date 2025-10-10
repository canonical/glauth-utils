# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import re
from enum import Enum
from re import Pattern
from typing import Final

GLAUTH_UTILS_LOGGING_ID: Final[str] = "identity_platform.glauth_utils_operator"

AUXILIARY_INTEGRATION_NAME = "glauth-auxiliary"

USER_IDENTIFIER_ATTRIBUTE: Final[str] = "cn"

GROUP_IDENTIFIER_ATTRIBUTE: Final[str] = "ou"

LDIF_PARSER_IGNORED_ATTRIBUTES: Final[set[str]] = {"objectClass"}

LDIF_SANITIZE_ATTRIBUTES: Final[set[str]] = {
    "changetype",
    "add",
    "replace",
    "delete",
    "deleteoldrdn",
    "newrdn",
    "newsuperior",
    "objectClass",
}

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

CUSTOM_ADDITIONAL_ATTRIBUTES: Final[set[str]] = {
    "newParentGroup",
}

SUPPORTED_LDIF_ATTRIBUTES: Final[set[str]] = (
    LDIF_TO_USER_MODEL_MAPPINGS
    | LDIF_TO_GROUP_MODEL_MAPPINGS
    | LDIF_TO_INCLUDE_GROUP_MODEL_MAPPINGS
).keys() | CUSTOM_ADDITIONAL_ATTRIBUTES

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


# Match "cn" or "ou" in a DN
# e.g. "cn=hackers,ou=superheros,dc=glauth,dc=com"
# The "id_attribute" group is "cn" and the "identifier" group is "hackers"
IDENTIFIER_REGEX: Final[Pattern] = re.compile(
    r"""
    ^(?P<id_attribute>cn|ou)
    =
    (?P<identifier>.+?)
    ,
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Match "newrdn" attribute in an LDIF record
# e.g. "newrdn: cn=hackers"
# The "newrdn" group is "hackers"
NEWRDN_REGEX: Final[Pattern] = re.compile(r"^cn=(?P<newrdn>[^,]+)", re.IGNORECASE)


# Match all "ou" in a DN
# e.g. "ou=superheros,ou=caped,ou=human,dc=glauth,dc=com"
# The "ou" group includes "superheros", "caped", and "human"
GROUP_HIERARCHY_REGEX: Final[Pattern] = re.compile(
    r"ou=([^,]+)",
    re.IGNORECASE,
)


# Match "userPassword" attribute in an LDIF record
# e.g. "userPassword: {SHA256}abc
# The "prefix" group is "SHA256" and the "password" group is "abc"
PASSWORD_REGEX: Final[Pattern] = re.compile(
    r"""
    ^{(?P<prefix>.+?)}
    (?P<password>.+$)
    """,
    re.IGNORECASE | re.VERBOSE,
)
