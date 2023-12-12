import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Type

from constant import (
    LDIF_SANITIZE_ATTRIBUTES,
    PASSWORD_ALGORITHM_REGISTRY,
    SUPPORTED_LDIF_ATTRIBUTES,
    USER_IDENTIFIER_ATTRIBUTE,
    OperationType,
)
from database import Base, Group, User
from ldif import LDIFRecordList

IDENTIFIER_REGEX = re.compile(r"^(?P<model>cn|ou)=(?P<identifier>.*?),", re.IGNORECASE)
PASSWORD_REGEX = re.compile(r"^{(?P<prefix>.*?)}(?P<password>.*$)", re.IGNORECASE)


@dataclass
class Record:
    identifier: Literal["cn", "ou"] = USER_IDENTIFIER_ATTRIBUTE
    model: Type[Base] = Type[User]
    op: OperationType = OperationType.CREATE
    attributes: dict[str, Any] = field(default_factory=dict)
    custom_attributes: dict[str, Any] = field(default_factory=dict)


Processor = Callable[[str, dict, Record], None]


def stringify_processor(dn: str, entry: dict, record: Record) -> None:
    for k, v in entry.items():
        entry[k] = v[0].decode("utf-8")


def dn_processor(dn: str, entry: dict, record: Record) -> None:
    if not (matched := IDENTIFIER_REGEX.search(dn)):
        return

    record.identifier = matched.group("identifier")
    record.model = (
        User if matched.group("model").casefold() == USER_IDENTIFIER_ATTRIBUTE else Group
    )


def password_processor(dn: str, entry: dict, record: Record) -> None:
    if not (password := entry.get("userPassword")):
        return

    if not (matched := PASSWORD_REGEX.search(password)):
        return

    prefix = matched.group("prefix").casefold()
    hashed_password = matched.group("password")

    entry[PASSWORD_ALGORITHM_REGISTRY[prefix]] = hashed_password
    entry.pop("userPassword", None)


def operation_processor(dn: str, entry: dict, record: None) -> None:
    match entry.get("changetype"):
        case "modrdn" | "moddn" if "newsuperior" in entry:
            record.op = OperationType.MOVE
            entry["ou"] = IDENTIFIER_REGEX.search(entry["newsuperior"]).group("identifier")
            return

        case "modrdn" | "moddn" if "newrdn" in entry:
            record.op = OperationType.UPDATE
            return

        case "modify":
            record.op = OperationType.UPDATE
            if "delete" in entry:
                entry[entry["delete"]] = ""
            return

        case "delete":
            record.op = OperationType.DELETE
            return

        case _:
            record.op = OperationType.CREATE


def attribute_processor(dn: str, entry: dict, record: Record) -> None:
    for sanitized_attribute in LDIF_SANITIZE_ATTRIBUTES:
        entry.pop(sanitized_attribute, None)

    supported_attributes = {k: v for k, v in entry.items() if k in SUPPORTED_LDIF_ATTRIBUTES}

    record.attributes = supported_attributes


def custom_attribute_processor(dn: str, entry: dict, record: Record) -> None:
    unsupported_attributes = {k: v for k, v in entry.items() if k not in SUPPORTED_LDIF_ATTRIBUTES}

    if record.model is User:
        record.custom_attributes = unsupported_attributes


class Parser(LDIFRecordList):
    def __init__(self, input_file, ignored_attr_types=None):
        super().__init__(input_file, ignored_attr_types)
        self.processors: Iterable[Processor] = [
            stringify_processor,
            dn_processor,
            password_processor,
            operation_processor,
            attribute_processor,
            custom_attribute_processor,
        ]

    def handle(self, dn, entry):
        record = Record()
        for processor in self.processors:
            processor(dn, entry, record)

        self.all_records.append(record)
