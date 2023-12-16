from abc import ABC, abstractmethod
from typing import Callable, Type

from constant import LDIF_TO_GROUP_MODEL_MAPPINGS, LDIF_TO_USER_MODEL_MAPPINGS, OperationType
from database import Base, Group, User
from parser import Record
from sqlalchemy import ScalarResult, select
from sqlalchemy.orm import Session

LDIF_MODEL_MAPPINGS = {
    User: LDIF_TO_USER_MODEL_MAPPINGS,
    Group: LDIF_TO_GROUP_MODEL_MAPPINGS,
}


def op_method_register(cls: "Operation"):
    for method_name in dir(cls):
        method = getattr(cls, method_name)
        if hasattr(method, "_op"):
            cls._op_registry[method._op] = method
    return cls


def op_label(op: OperationType) -> Callable:
    def decorator(func: Callable) -> Callable:
        func._op = op
        return func

    return decorator


class Operation(ABC):
    _op_registry: dict[OperationType, Callable] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._op_registry = {}

    @classmethod
    def get_registry(cls, op: OperationType):
        return cls._op_registry.get(op)

    def select(self, session: Session, model: Type[Base], criteria: dict) -> ScalarResult[Base]:
        res = session.scalars(select(model).filter_by(**criteria))
        return res

    def create(self, session: Session, record: Record) -> None:
        attribute_mapping = LDIF_MODEL_MAPPINGS[record.model]

        attributes = {attribute_mapping[k]: v for k, v in record.attributes.items()}
        obj = record.model(**attributes)
        session.add(obj)

    def update(self, session: Session, record: Record) -> None:
        attribute_mapping = LDIF_MODEL_MAPPINGS[record.model]

        obj = self.select(session, record.model, criteria={"name": record.identifier}).first()
        if obj:
            for attr, value in record.attributes.items():
                setattr(obj, attribute_mapping[attr], value)

    def delete(self, session: Session, record: Record) -> None:
        obj = self.select(session, record.model, criteria={"name": record.identifier}).first()
        if obj:
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
        obj = self.select(session, record.model, criteria={"name": record.identifier}).first()
        if obj:
            for attr, value in record.attributes.items():
                setattr(obj, LDIF_TO_USER_MODEL_MAPPINGS[attr], value)

            if record.custom_attributes:
                obj.custom_attributes = {
                    **obj.custom_attributes,
                    **record.custom_attributes,
                }

    @op_label(OperationType.DELETE)
    def delete(self, session: Session, record: Record) -> None:
        super().delete(session, Record)

    @op_label(OperationType.MOVE)
    def move(self, session: Session, record: Record) -> None:
        obj = self.select(session, record.model, criteria={"name": record.identifier}).first()
        if obj:
            group = self.select(
                session, Group, criteria={"name": record.attributes.get("ou")}
            ).first()
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
        pass


OPERATIONS = {
    User: UserOperation,
    Group: GroupOperation,
}
