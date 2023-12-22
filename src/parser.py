import operator
import re
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Final, Iterable, List, Optional, TextIO, Type

from constant import (
    LDIF_SANITIZE_ATTRIBUTES,
    PASSWORD_ALGORITHM_REGISTRY,
    SUPPORTED_LDIF_ATTRIBUTES,
    USER_IDENTIFIER_ATTRIBUTE,
    OperationType,
)
from database import Base, Group, User
from ldif import LDIFRecordList

IDENTIFIER_REGEX: Final = re.compile(
    r"""
    ^(?P<id_attribute>cn|ou)
    =
    (?P<identifier>.*?),
    """,
    re.IGNORECASE | re.VERBOSE,
)
PASSWORD_REGEX: Final = re.compile(
    r"""
    ^{(?P<prefix>.*?)}
    (?P<password>.*$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

Processor = Callable[[str, dict, "Record"], None]

processor_chain: List[Processor] = []


@dataclass
class Record:
    identifier: str = USER_IDENTIFIER_ATTRIBUTE
    model: Type[Base] = User
    op: OperationType = OperationType.CREATE
    attributes: dict[str, Any] = field(default_factory=dict)
    custom_attributes: dict[str, Any] = field(default_factory=dict)


def chain_order(order: int) -> Callable:
    def decorator(func: Processor) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper.order = order
        processor_chain.append(wrapper)
        processor_chain.sort(key=operator.attrgetter("order"))
        return wrapper

    return decorator


@chain_order(order=1)
def stringify_processor(dn: str, entry: dict, record: Record) -> None:
    for k, v in entry.items():
        decoded = [i.decode("utf-8") for i in v]
        entry[k] = decoded if len(v) > 1 else decoded[0]


@chain_order(order=2)
def dn_processor(dn: str, entry: dict, record: Record) -> None:
    if not (matched := IDENTIFIER_REGEX.search(dn)):
        return

    record.model = (
        User if matched.group("id_attribute").casefold() == USER_IDENTIFIER_ATTRIBUTE else Group
    )
    record.identifier = matched.group("identifier")


@chain_order(order=3)
def password_processor(dn: str, entry: dict, record: Record) -> None:
    if not (password := entry.get("userPassword")):
        return

    if not (matched := PASSWORD_REGEX.search(password)):
        return

    prefix = matched.group("prefix").casefold()
    hashed_password = matched.group("password")

    entry[PASSWORD_ALGORITHM_REGISTRY[prefix]] = hashed_password
    entry.pop("userPassword", None)


@chain_order(order=4)
def operation_processor(dn: str, entry: dict, record: Record) -> None:
    match entry.get("changetype"):
        case "modrdn" | "moddn" if "newsuperior" in entry:
            record.op = OperationType.MOVE
            if not (matched := IDENTIFIER_REGEX.search(entry["newsuperior"])):
                raise ValueError(
                    f"Invalid entry attribute in the LDIF file: {entry['newsuperior']}"
                )

            entry["ou"] = matched.group("identifier")
            return

        case "modrdn" | "moddn" if "newrdn" in entry:
            record.op = OperationType.UPDATE
            return

        case "modify" if "memberUid" in entry:
            record.op = OperationType.ATTACH if "add" in entry else OperationType.DETACH
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


@chain_order(order=5)
def attribute_processor(dn: str, entry: dict, record: Record) -> None:
    for sanitized_attribute in LDIF_SANITIZE_ATTRIBUTES:
        entry.pop(sanitized_attribute, None)

    supported_attributes = {k: v for k, v in entry.items() if k in SUPPORTED_LDIF_ATTRIBUTES}

    record.attributes = supported_attributes


@chain_order(order=6)
def custom_attribute_processor(dn: str, entry: dict, record: Record) -> None:
    if record.model is not User:
        return

    unsupported_attributes = {k: v for k, v in entry.items() if k not in SUPPORTED_LDIF_ATTRIBUTES}
    record.custom_attributes = unsupported_attributes


class Parser(LDIFRecordList):
    def __init__(self, input_file: TextIO, ignored_attr_types: Optional[Iterable[str]] = None):
        super().__init__(input_file, ignored_attr_types)

    def handle(self, dn: str, entry: dict) -> None:
        record = Record()
        for processor in processor_chain:
            processor(dn, entry, record)

        self.all_records.append(record)
