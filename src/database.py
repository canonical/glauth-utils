# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from typing import List, Optional

from sqlalchemy import Dialect, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TEXT, VARCHAR, TypeDecorator


class JsonEncodeDict(TypeDecorator):
    impl = VARCHAR

    cache_ok = True

    def process_bind_param(self, value: Optional[dict], dialect: Dialect):
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value: Optional[str], dialect: Dialect):
        return json.loads(value) if value is not None else None


class GroupSet(TypeDecorator):
    impl = TEXT

    cache_ok = True

    def process_bind_param(self, value: Optional[set], dialect: Dialect):
        return ",".join(list(value)) if value else ""

    def process_result_value(self, value: Optional[str], dialect: Dialect):
        return set(value.split(",")) if value else set()


class Base(DeclarativeBase):
    pass


# https://github.com/glauth/glauth-postgres/blob/main/postgres.go
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, name="name", unique=True)
    uid_number: Mapped[int] = mapped_column(name="uidnumber")
    gid_number: Mapped[int] = mapped_column(
        ForeignKey("ldapgroups.gidnumber", onupdate="cascade"),
        name="primarygroup",
    )
    other_groups: Mapped[set] = mapped_column(GroupSet, name="othergroups")
    given_name: Mapped[Optional[str]] = mapped_column(name="givenname")
    surname: Mapped[Optional[str]] = mapped_column(name="sn")
    email: Mapped[Optional[str]] = mapped_column(name="mail")
    login_shell: Mapped[Optional[str]] = mapped_column(name="loginshell")
    home_directory: Mapped[Optional[str]] = mapped_column(name="homedirectory")
    disabled = mapped_column(SmallInteger, default=0)
    password_sha256: Mapped[Optional[str]] = mapped_column(name="passsha256", default="")
    password_bcrypt: Mapped[Optional[str]] = mapped_column(name="passbcrypt", default="")
    otp_secret: Mapped[Optional[str]] = mapped_column(name="otpsecret")
    yubi_key: Mapped[Optional[str]] = mapped_column(name="yubikey")
    ssh_keys: Mapped[Optional[str]] = mapped_column(name="sshkeys")
    custom_attributes: Mapped[Optional[dict]] = mapped_column(JsonEncodeDict, name="custattr")

    group: Mapped["Group"] = relationship(back_populates="users")


class Group(Base):
    __tablename__ = "ldapgroups"

    id = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(name="name", unique=True)
    gid_number: Mapped[int] = mapped_column(name="gidnumber")

    users: Mapped[List["User"]] = relationship(back_populates="group")


class IncludeGroup(Base):
    __tablename__ = "includegroups"

    id = mapped_column(Integer, primary_key=True)
    parent_group_id: Mapped[int] = mapped_column(
        ForeignKey("ldapgroups.gidnumber", onupdate="cascade"),
        name="parentgroupid",
    )
    child_group_id: Mapped[int] = mapped_column(
        ForeignKey("ldapgroups.gidnumber", onupdate="cascade"),
        name="includegroupid",
    )

    parent_group: Mapped["Group"] = relationship("Group", foreign_keys=[parent_group_id])
    child_group: Mapped["Group"] = relationship("Group", foreign_keys=[child_group_id])


class Capability(Base):
    __tablename__ = "capabilities"

    id = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(name="userid")
    action: Mapped[str] = mapped_column(default="search")
    object: Mapped[str]
