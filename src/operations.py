from abc import ABC, abstractmethod
from typing import Callable, Final, Optional, Type, TypeVar

from constant import (
    LDIF_TO_GROUP_MODEL_MAPPINGS,
    LDIF_TO_INCLUDE_GROUP_MODEL_MAPPINGS,
    LDIF_TO_USER_MODEL_MAPPINGS,
    OperationType,
)
from database import Base, Group, IncludeGroup, User
from parser import Record
from sqlalchemy import ColumnExpressionArgument, ScalarResult, select
from sqlalchemy.orm import Session

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


def op_label(op: OperationType) -> Callable:
    def decorator(func: Method) -> Method:
        func._op = op
        return func

    return decorator


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

        attributes = {attribute_mapping[k]: v for k, v in record.attributes.items()}
        obj = record.model(**attributes)
        session.add(obj)

    def update(self, session: Session, record: Record) -> None:
        if not (
            obj := self.select(session, record.model, record.model.name == record.identifier)
        ).first():
            return

        attribute_mapping = LDIF_MODEL_MAPPINGS[record.model]
        for attr, value in record.attributes.items():
            setattr(obj, attribute_mapping[attr], value)

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
        attributes = {LDIF_TO_USER_MODEL_MAPPINGS[k]: v for k, v in record.attributes.items()}
        obj = record.model(**attributes)

        if record.custom_attributes:
            obj.custom_attributes = record.custom_attributes

        session.add(obj)

    @op_label(OperationType.UPDATE)
    def update(self, session: Session, record: Record) -> None:
        if not (obj := self.select(session, User, User.name == record.identifier).first()):
            return

        for attr, value in record.attributes.items():
            setattr(obj, LDIF_TO_USER_MODEL_MAPPINGS[attr], value)

        if record.custom_attributes:
            obj.custom_attributes = {
                **obj.custom_attributes,
                **record.custom_attributes,
            }

    @op_label(OperationType.DELETE)
    def delete(self, session: Session, record: Record) -> None:
        super().delete(session, record)

    @op_label(OperationType.MOVE)
    def move(self, session: Session, record: Record) -> None:
        if not (obj := self.select(session, User, User.name == record.identifier).first()):
            return

        group = self.select(session, Group, Group.name == record.attributes.get("ou"))
        obj.group = group


@op_method_register
class GroupOperation(Operation):
    @op_label(OperationType.CREATE)
    def create(self, session: Session, record: Record) -> None:
        super().create(session, record)

    @op_label(OperationType.UPDATE)
    def update(self, session: Session, record: Record) -> None:
        super().update(session, record)

    @op_label(OperationType.DELETE)
    def delete(self, session: Session, record: Record) -> None:
        super().delete(session, record)

    @op_label(OperationType.MOVE)
    def move(self, session: Session, record: Record) -> None:
        group = self.select(session, Group, Group.name == record.identifier).first()
        parent_group = self.select(
            session, Group, Group.name == record.attributes.get("ou")
        ).first()

        if association := self.select(
            session, IncludeGroup, IncludeGroup.child_group == group
        ).first():
            association.parent_group = parent_group
            return

        include_group_record = Record(
            identifier="ou",
            model=IncludeGroup,
            attributes={"parentGroup": parent_group, "childGroup": group},
        )
        self.create(session, include_group_record)

    @op_label(OperationType.ATTACH)
    def attach(self, session: Session, record: Record) -> None:
        if not (group := self.select(session, Group, Group.name == record.identifier).first()):
            return

        uid_numbers = [int(uid) for uid in record.attributes.get("memberUid")]
        users = self.select(session, User, User.uid_number.in_(uid_numbers)).all()
        for user in users:
            user.other_groups = user.other_groups | {str(group.gid_number)}

    @op_label(OperationType.DETACH)
    def detach(self, session: Session, record: Record) -> None:
        if not (group := self.select(session, Group, Group.name == record.identifier).first()):
            return

        uid_numbers = [int(uid) for uid in record.attributes.get("memberUid")]
        users = self.select(session, User, User.uid_number.in_(uid_numbers)).all()
        for user in users:
            user.other_groups = user.other_groups - {str(group.gid_number)}


OPERATIONS: Final[dict] = {
    User: UserOperation,
    Group: GroupOperation,
}
