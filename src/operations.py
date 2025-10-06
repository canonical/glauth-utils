# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod
from dataclasses import replace
from logging import WARN
from parser import Record
from typing import Callable, Final, Optional, Type, TypeVar

from sqlalchemy import ColumnExpressionArgument, ScalarResult, select
from sqlalchemy.orm import Session

from constants import (
    GLAUTH_UTILS_LOGGING_ID,
    LDIF_TO_GROUP_MODEL_MAPPINGS,
    LDIF_TO_INCLUDE_GROUP_MODEL_MAPPINGS,
    LDIF_TO_USER_MODEL_MAPPINGS,
    OperationType,
)
from database import Base, Group, IncludeGroup, User
from security_logging import OWASPLogger

security_logger = OWASPLogger(appid=GLAUTH_UTILS_LOGGING_ID)

LDIF_MODEL_MAPPINGS = {
    User: LDIF_TO_USER_MODEL_MAPPINGS,
    Group: LDIF_TO_GROUP_MODEL_MAPPINGS,
    IncludeGroup: LDIF_TO_INCLUDE_GROUP_MODEL_MAPPINGS,
}

Method = TypeVar("Method", bound=Callable)


def op_method_register(cls: Type["Operation"]) -> Type["Operation"]:
    for method_name in dir(cls):
        method = getattr(cls, method_name)
        if hasattr(method, "_op"):
            cls._op_registry[method._op] = method
    return cls


def op_label(op: OperationType) -> Callable[[Method], Method]:
    def decorator(func: Method) -> Method:
        func._op = op
        return func

    return decorator


# How SQLAlchemy session persists data to the database:
# https://docs.sqlalchemy.org/en/20/glossary.html#term-unit-of-work
class Operation(ABC):
    _op_registry: dict[OperationType, Callable] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._op_registry = {}

    @classmethod
    def get_registry(cls, op: OperationType) -> Optional[Callable]:
        return cls._op_registry.get(op)

    def select(
        self, session: Session, model: Type[Base], *criteria: ColumnExpressionArgument
    ) -> ScalarResult[Base]:
        res = session.scalars(select(model).filter(*criteria))
        return res

    def create(self, session: Session, record: Record) -> None:
        attribute_mapping = LDIF_MODEL_MAPPINGS[record.model]

        attributes = {
            attribute_mapping[k]: v for k, v in record.attributes.items() if k in attribute_mapping
        }
        obj = record.model(**attributes)
        session.add(obj)

    def update(self, session: Session, record: Record) -> None:
        if not (
            obj := self.select(
                session, record.model, record.model.name == record.identifier
            ).first()
        ):
            return

        attribute_mapping = LDIF_MODEL_MAPPINGS[record.model]
        for attr, value in record.attributes.items():
            if mapped_attr := attribute_mapping.get(attr):
                setattr(obj, mapped_attr, value)

    def delete(self, session: Session, record: Record) -> None:
        if obj := self.select(
            session, record.model, record.model.name == record.identifier
        ).first():
            session.delete(obj)

    @abstractmethod
    def move(self, session: Session, record: Record) -> None:
        pass


@op_method_register
class UserOperation(Operation):
    @op_label(OperationType.CREATE)
    def create(self, session: Session, record: Record) -> None:
        attributes = {
            LDIF_TO_USER_MODEL_MAPPINGS[k]: v
            for k, v in record.attributes.items()
            if k in LDIF_TO_USER_MODEL_MAPPINGS
        }
        obj = record.model(**attributes)

        if record.custom_attributes:
            obj.custom_attributes = record.custom_attributes

        security_logger.log_event(
            event=f"authz_admin:user_created:{record.identifier}",
            level=WARN,
            description=f"User `{record.identifier}` was created",
            user=record.identifier,
        )

        session.add(obj)

    @op_label(OperationType.UPDATE)
    def update(self, session: Session, record: Record) -> None:
        if not (obj := self.select(session, User, User.name == record.identifier).first()):
            return

        for attr, value in record.attributes.items():
            if mapped_attr := LDIF_TO_USER_MODEL_MAPPINGS.get(attr):
                setattr(obj, mapped_attr, value)

        if record.custom_attributes:
            obj.custom_attributes = {
                **obj.custom_attributes,
                **record.custom_attributes,
            }

        security_logger.log_event(
            event=f"authz_admin:user_updated:{record.identifier}",
            level=WARN,
            description=f"User `{record.identifier}` was updated",
            user=record.identifier,
        )

    @op_label(OperationType.DELETE)
    def delete(self, session: Session, record: Record) -> None:
        super().delete(session, record)
        security_logger.log_event(
            event=f"authz_admin:user_deleted:{record.identifier}",
            level=WARN,
            description=f"User `{record.identifier}` was deleted",
            user=record.identifier,
        )

    @op_label(OperationType.MOVE)
    def move(self, session: Session, record: Record) -> None:
        if not (obj := self.select(session, User, User.name == record.identifier).first()):
            return

        group = self.select(session, Group, Group.name == record.attributes.get("ou")).first()
        obj.group = group
        security_logger.log_event(
            event=f"authz_admin:user_moved:{record.identifier}",
            level=WARN,
            description=f"User `{record.identifier}` was moved to a different group",
            group=group.name,
            user=record.identifier,
        )


@op_method_register
class GroupOperation(Operation):
    @op_label(OperationType.CREATE)
    def create(self, session: Session, record: Record) -> None:
        super().create(session, record)
        match record.attributes:
            case {"parentGroup": parent_group} if parent_group:
                association_record = replace(record)
                association_record.op = OperationType.MOVE
                association_record.attributes["newParentGroup"] = parent_group
                self.move(session, association_record)
            case _:
                return

        security_logger.log_event(
            event=f"authz_admin:group_created:{record.identifier}",
            level=WARN,
            description=f"Group `{record.identifier}` was created",
            parent_group=record.attributes.get("parentGroup"),
            group=record.identifier,
        )

    @op_label(OperationType.UPDATE)
    def update(self, session: Session, record: Record) -> None:
        super().update(session, record)
        security_logger.log_event(
            event=f"authz_admin:group_updated:{record.identifier}",
            level=WARN,
            description=f"Group `{record.identifier}` was updated",
            group=record.identifier,
        )

    @op_label(OperationType.DELETE)
    def delete(self, session: Session, record: Record) -> None:
        super().delete(session, record)
        security_logger.log_event(
            event=f"authz_admin:group_deleted:{record.identifier}",
            level=WARN,
            description=f"Group `{record.identifier}` was deleted",
            group=record.identifier,
        )

    @op_label(OperationType.MOVE)
    def move(self, session: Session, record: Record) -> None:
        group = self.select(session, Group, Group.name == record.identifier).first()
        parent_group = self.select(
            session, Group, Group.name == record.attributes.get("parentGroup")
        ).first()
        new_parent_group = self.select(
            session, Group, Group.name == record.attributes.get("newParentGroup")
        ).first()

        if association := self.select(
            session,
            IncludeGroup,
            IncludeGroup.parent_group == parent_group,
            IncludeGroup.child_group == group,
        ).first():
            association.parent_group = new_parent_group
            security_logger.log_event(
                event=f"authz_admin:group_updated:{record.identifier}",
                level=WARN,
                description=f"Changed parent of group `{record.identifier}`",
                group=record.identifier,
                parent_group=record.attributes.get("newParentGroup"),
            )
            return

        include_group_record = Record(
            identifier="ou",
            model=IncludeGroup,
            attributes={"parentGroup": new_parent_group, "childGroup": group},
        )
        super().create(session, include_group_record)

    @op_label(OperationType.ATTACH)
    def attach(self, session: Session, record: Record) -> None:
        if not (group := self.select(session, Group, Group.name == record.identifier).first()):
            return

        member_uid = record.attributes["memberUid"]
        if not isinstance(member_uid, list):
            member_uid = [member_uid]

        uid_numbers = [int(uid) for uid in member_uid]
        users = self.select(session, User, User.uid_number.in_(uid_numbers)).all()
        for user in users:
            user.other_groups = user.other_groups | {str(group.gid_number)}

        security_logger.log_event(
            event=f"authz_admin:group_attached:{record.identifier}",
            level=WARN,
            description=f"Attached users to group `{record.identifier}`",
            group=record.identifier,
            uids=",".join(map(str, uid_numbers)),
        )

    @op_label(OperationType.DETACH)
    def detach(self, session: Session, record: Record) -> None:
        if not (group := self.select(session, Group, Group.name == record.identifier).first()):
            return

        member_uid = record.attributes["memberUid"]
        if not isinstance(member_uid, list):
            member_uid = [member_uid]

        uid_numbers = [int(uid) for uid in member_uid]
        users = self.select(session, User, User.uid_number.in_(uid_numbers)).all()
        for user in users:
            user.other_groups = user.other_groups - {str(group.gid_number)}

        security_logger.log_event(
            event=f"authz_admin:group_detached:{record.identifier}",
            level=WARN,
            description=f"Detached users from group `{record.identifier}`",
            group=record.identifier,
            uids=",".join(map(str, uid_numbers)),
        )


OPERATIONS: Final[dict] = {
    User: UserOperation,
    Group: GroupOperation,
}
