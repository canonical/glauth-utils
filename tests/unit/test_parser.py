# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from constants import (
    LDIF_SANITIZE_ATTRIBUTES,
    SUPPORTED_LDIF_ATTRIBUTES,
    OperationType,
)
from database import Group, User
from exceptions import InvalidAttributeValueError, InvalidDistinguishedNameError
from parser import (
    Record,
    attribute_processor,
    custom_attribute_processor,
    dn_processor,
    entry_validation_processor,
    operation_processor,
    password_processor,
    stringify_processor,
)


class TestStringifyProcessor:
    def test_with_single_attribute_value(
        self, user_dn: str, raw_user_entry: dict, record: Record
    ) -> None:
        stringify_processor(user_dn, raw_user_entry, record)

        assert all(
            (isinstance(value, str) for value in raw_user_entry.values()),
        ), "All attribute values should be of type str."

    def test_with_multi_attribute_values(self, user_dn: str, record: Record) -> None:
        entry = {"ability": [b"hacking", b"fly"]}
        stringify_processor(user_dn, entry, record)

        assert ["hacking", "fly"] == entry[
            "ability"
        ], "All elements in an attribute should be of type str."


class TestEntryValidationProcessor:
    @pytest.mark.parametrize(
        "dn",
        [
            "cn=hackers",
            "x=hackers,ou=superheros,dc=glauth,dc=com",
        ],
    )
    def test_invalid_dn(self, dn: str, stringify_user_entry: dict, record: Record) -> None:
        with pytest.raises(InvalidDistinguishedNameError):
            entry_validation_processor(dn, stringify_user_entry, record)

    @pytest.mark.parametrize(
        "password",
        [
            {"userPassword": "xyz"},
            {"userPassword": "{}xyz"},
            {"userPassword": "{SHA256}"},
        ],
    )
    def test_invalid_password(
        self, password: dict, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {**stringify_user_entry, **password}
        with pytest.raises(InvalidAttributeValueError):
            entry_validation_processor(user_dn, entry, user_record)

    def test_invalid_newsuperior(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {**stringify_user_entry, "newsuperior": "ou=svcaccts"}
        with pytest.raises(InvalidAttributeValueError) as exc:
            entry_validation_processor(user_dn, entry, user_record)

        assert "Invalid newsuperior" in str(exc)

    def test_invalid_newrdn(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {**stringify_user_entry, "newrdn": "ou=svcaccts"}
        with pytest.raises(InvalidAttributeValueError) as exc:
            entry_validation_processor(user_dn, entry, user_record)

        assert "Invalid newrdn" in str(exc)

    @pytest.mark.parametrize(
        "member_uid",
        [
            {"memberUid": "xyz"},
            {"memberUid": ["5001", "xyz"]},
        ],
    )
    def test_invalid_member_uid(
        self,
        member_uid: dict,
        user_dn: str,
        stringify_user_entry: dict,
        user_record: Record,
    ) -> None:
        entry = {**stringify_user_entry, **member_uid}
        with pytest.raises(InvalidAttributeValueError) as exc:
            entry_validation_processor(user_dn, entry, user_record)

        assert "Invalid memberUid" in str(exc)


class TestDnProcessor:
    def test_user_dn(self, user_dn: str, stringify_user_entry: dict, record: Record) -> None:
        dn_processor(user_dn, stringify_user_entry, record)
        assert User == record.model
        assert stringify_user_entry["cn"] == record.identifier

    def test_group_dn(self, group_dn: str, stringify_group_entry: dict, record: Record) -> None:
        dn_processor(group_dn, stringify_group_entry, record)
        assert Group == record.model
        assert stringify_group_entry["ou"] == record.identifier


class TestPasswordProcessor:
    def test_process_password(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {**stringify_user_entry, "userPassword": "{BCRYPT}xyz"}
        password_processor(user_dn, entry, user_record)

        assert (
            "userPassword" not in entry and "passwordBcrypt" in entry
        ), "Password attribute should be mapped."


class TestOperationProcessor:
    @pytest.mark.parametrize(
        "change_type",
        ["modrdn", "moddn"],
    )
    def test_move_user(
        self, change_type: str, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {
            **stringify_user_entry,
            "changetype": change_type,
            "newsuperior": "ou=svcaccts,dc=glauth,dc=com",
        }
        operation_processor(user_dn, entry, user_record)

        assert OperationType.MOVE == user_record.op
        assert "svcaccts" == entry["ou"], "User's group should be the new superior."

    @pytest.mark.parametrize(
        "change_type",
        ["modrdn", "moddn"],
    )
    @pytest.mark.parametrize(
        "dn,parent",
        [
            ("ou=superheros,dc=glauth,dc=com", ""),
            ("ou=superheros,ou=caped,dc=glauth,dc=com", "caped"),
        ],
    )
    def test_move_group(
        self,
        dn: str,
        change_type: str,
        parent: str,
        stringify_user_entry: dict,
        group_record: Record,
    ) -> None:
        entry = {
            **stringify_user_entry,
            "changetype": change_type,
            "newsuperior": "ou=svcaccts,dc=glauth,dc=com",
        }
        operation_processor(dn, entry, group_record)

        assert OperationType.MOVE == group_record.op
        assert (
            "svcaccts" == entry["newParentGroup"]
        ), "Group's new parent should be the new superior."
        assert parent == entry["parentGroup"]

    @pytest.mark.parametrize(
        "change_type",
        ["modrdn", "moddn"],
    )
    def test_rename_user(
        self, change_type: str, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {
            **stringify_user_entry,
            "changetype": change_type,
            "newrdn": "cn=serviceuser",
        }
        operation_processor(user_dn, entry, user_record)

        assert OperationType.UPDATE == user_record.op

    def test_attach_user(
        self, group_dn: str, stringify_group_entry: dict, group_record: Record
    ) -> None:
        entry = {
            **stringify_group_entry,
            "changetype": "modify",
            "add": "memberUid",
            "memberUid": "5001",
        }
        operation_processor(group_dn, entry, group_record)

        assert OperationType.ATTACH == group_record.op

    def test_detach_user(
        self, group_dn: str, stringify_group_entry: dict, group_record: Record
    ) -> None:
        entry = {
            **stringify_group_entry,
            "changetype": "modify",
            "delete": "memberUid",
            "memberUid": "5001",
        }
        operation_processor(group_dn, entry, group_record)

        assert OperationType.DETACH == group_record.op

    def test_modify_attribute(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {
            **stringify_user_entry,
            "changetype": "modify",
        }
        operation_processor(user_dn, entry, user_record)

        assert OperationType.UPDATE == user_record.op

    def test_delete_attribute(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {
            **stringify_user_entry,
            "changetype": "modify",
            "delete": "mail",
        }
        operation_processor(user_dn, entry, user_record)

        assert OperationType.UPDATE == user_record.op
        assert "" == entry["mail"], "Mail attribute should be deleted."

    def test_delete_record(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {
            **stringify_user_entry,
            "changetype": "delete",
        }
        operation_processor(user_dn, entry, user_record)

        assert OperationType.DELETE == user_record.op

    def test_add_record(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        operation_processor(user_dn, stringify_user_entry, user_record)

        assert OperationType.CREATE == user_record.op


class TestAttributeProcessor:
    def test_sanitize_attributes(
        self, user_dn: str, stringify_user_entry: dict, user_record: Record
    ) -> None:
        entry = {**stringify_user_entry, **dict.fromkeys(LDIF_SANITIZE_ATTRIBUTES, "")}
        attribute_processor(user_dn, entry, user_record)

        assert not (
            user_record.attributes.keys() & LDIF_SANITIZE_ATTRIBUTES
        ), "Attributes should not contain sanitized attributes."

    def test_supported_attributes(self, user_dn: str, user_record: Record) -> None:
        entry = {
            **dict.fromkeys(SUPPORTED_LDIF_ATTRIBUTES, ""),
            "unsupported": "unsupported",
        }
        attribute_processor(user_dn, entry, user_record)

        assert "unsupported" not in user_record.attributes
        assert SUPPORTED_LDIF_ATTRIBUTES == user_record.attributes.keys()


class TestCustomAttributeProcessor:
    def test_group_attributes(
        self, group_dn: str, stringify_group_entry: dict, group_record: Record
    ):
        custom_attribute_processor(group_dn, stringify_group_entry, group_record)

        assert not group_record.custom_attributes, "Group does not support custom attributes"

    def test_unsupported_attributes(self, user_dn: str, user_record: Record) -> None:
        entry = {
            **dict.fromkeys(SUPPORTED_LDIF_ATTRIBUTES, ""),
            "unsupported": "unsupported",
        }
        custom_attribute_processor(user_dn, entry, user_record)

        assert "unsupported" not in user_record.attributes
        assert (
            "unsupported" == user_record.custom_attributes["unsupported"]
        ), "Any unsupported attributes should be mapped to custom attributes"
