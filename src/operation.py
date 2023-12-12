import json
from functools import wraps
from typing import Callable

from constant import LDIF_TO_GROUP_MODEL_MAPPINGS, LDIF_TO_USER_MODEL_MAPPINGS, OperationType
from database import Group, User
from parser import Record
from sqlalchemy import select
from sqlalchemy.orm import Session

LDIF_MODEL_MAPPINGS = {
    User: LDIF_TO_USER_MODEL_MAPPINGS,
    Group: LDIF_TO_GROUP_MODEL_MAPPINGS,
}

operation_registry = {}

Operation = Callable[[Session, Record], None]


def operation(op: OperationType):
    def decorator(func: Operation):
        operation_registry[op] = func

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


@operation(OperationType.MOVE)
def move_user_operation(session: Session, record: Record) -> None:
    obj = session.scalars(select(record.model).filter_by(name=record.identifier)).first()

    if obj:
        group_name = record.attributes.get("ou")
        group = session.scalars(select(Group).filter_by(name=group_name)).first()
        obj.group = group


@operation(OperationType.CREATE)
def create_operation(session: Session, record: Record) -> None:
    attribute_mapping = LDIF_MODEL_MAPPINGS[record.model]

    attributes = {attribute_mapping[k]: v for k, v in record.attributes.items()}
    obj = record.model(**attributes)

    if record.custom_attributes:
        obj.custom_attributes = record.custom_attributes

    session.add(obj)


@operation(OperationType.UPDATE)
def update_operation(session: Session, record: Record) -> None:
    attribute_mapping = LDIF_MODEL_MAPPINGS[record.model]

    obj = session.scalars(select(record.model).filter_by(name=record.identifier)).first()

    if obj:
        for attr, value in record.attributes.items():
            setattr(obj, attribute_mapping[attr], value)

        if record.custom_attributes:
            obj.custom_attributes = {
                **json.loads(obj.custom_attributes),
                **record.custom_attributes,
            }


@operation(OperationType.DELETE)
def delete_operation(session: Session, record: Record) -> None:
    obj = session.scalars(select(record.model).filter_by(name=record.identifier)).first()
    if obj:
        session.delete(obj)
