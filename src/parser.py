# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import operator
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Iterable, List, Optional, TextIO, Type

from ldif import LDIFRecordList

from constants import (
    GROUP_HIERARCHY_REGEX,
    IDENTIFIER_REGEX,
    LDIF_SANITIZE_ATTRIBUTES,
    NEWRDN_REGEX,
    PASSWORD_ALGORITHM_REGISTRY,
    PASSWORD_REGEX,
    SUPPORTED_LDIF_ATTRIBUTES,
    USER_IDENTIFIER_ATTRIBUTE,
    OperationType,
)
from database import Base, Group, User
from exceptions import InvalidAttributeValueError, InvalidDistinguishedNameError

Processor = Callable[[str, dict, "Record"], None]

processor_chain: List[Processor] = []


@dataclass
class Record:
    identifier: str = USER_IDENTIFIER_ATTRIBUTE
    model: Type[Base] = User
    op: OperationType = OperationType.CREATE
    attributes: dict[str, Any] = field(default_factory=dict)
    custom_attributes: dict[str, Any] = field(default_factory=dict)


def _extract_identifier(haystack: str) -> str:
    matched = IDENTIFIER_REGEX.search(haystack)
    return matched.group("identifier") if matched else ""


def _extract_group(haystack: str) -> str:
    _, *parents = GROUP_HIERARCHY_REGEX.findall(haystack)[:2]
    return parents[0] if parents else ""


def _extract_newrdn(haystack: str) -> str:
    matched = NEWRDN_REGEX.search(haystack)
    return matched.group("newrdn") if matched else ""


def chain_order(order: int) -> Callable[[Processor], Processor]:
    def decorator(func: Processor) -> Processor:
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
def entry_validation_processor(dn: str, entry: dict, record: Record):
    if not IDENTIFIER_REGEX.search(dn):
        raise InvalidDistinguishedNameError(f"Invalid DN: {dn}")

    if password := entry.get("userPassword"):
        if not PASSWORD_REGEX.search(password):
            raise InvalidAttributeValueError(f"Invalid password for DN: {dn}")

    if new_superior := entry.get("newsuperior"):
        if not IDENTIFIER_REGEX.search(new_superior):
            raise InvalidAttributeValueError(f"Invalid newsuperior for DN: {dn}")

    if newrdn := entry.get("newrdn"):
        if not NEWRDN_REGEX.search(newrdn):
            raise InvalidAttributeValueError(f"Invalid newrdn for DN: {dn}")

    if member_uid := entry.get("memberUid"):
        if not all(uid.isdigit() for uid in member_uid):
            raise InvalidAttributeValueError(f"Invalid memberUid for DN: {dn}")


@chain_order(order=3)
def dn_processor(dn: str, entry: dict, record: Record) -> None:
    matched = IDENTIFIER_REGEX.search(dn)
    record.model = (
        User if matched.group("id_attribute").casefold() == USER_IDENTIFIER_ATTRIBUTE else Group
    )
    record.identifier = matched.group("identifier")


@chain_order(order=4)
def password_processor(dn: str, entry: dict, record: Record) -> None:
    if not (password := entry.get("userPassword")):
        return

    matched = PASSWORD_REGEX.search(password)
    prefix = matched.group("prefix").casefold()
    hashed_password = matched.group("password")

    entry[PASSWORD_ALGORITHM_REGISTRY[prefix]] = hashed_password
    entry.pop("userPassword", None)


@chain_order(order=5)
def operation_processor(dn: str, entry: dict, record: Record) -> None:
    match entry.get("changetype"):
        case "modrdn" | "moddn" if ("newsuperior" in entry and record.model is User):
            record.op = OperationType.MOVE
            entry["ou"] = _extract_identifier(entry["newsuperior"])
            return

        case "modrdn" | "moddn" if ("newsuperior" in entry and record.model is Group):
            record.op = OperationType.MOVE
            entry["newParentGroup"] = _extract_identifier(entry["newsuperior"])
            entry["parentGroup"] = _extract_group(dn)
            return

        case "modrdn" | "moddn" if "newrdn" in entry:
            record.op = OperationType.UPDATE
            entry["cn"] = _extract_newrdn(entry["newrdn"])
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
            if record.model is not Group:
                return
            entry["parentGroup"] = _extract_group(dn)


@chain_order(order=6)
def attribute_processor(dn: str, entry: dict, record: Record) -> None:
    for sanitized_attribute in LDIF_SANITIZE_ATTRIBUTES:
        entry.pop(sanitized_attribute, None)

    supported_attributes = {k: v for k, v in entry.items() if k in SUPPORTED_LDIF_ATTRIBUTES}

    record.attributes = supported_attributes


@chain_order(order=7)
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
