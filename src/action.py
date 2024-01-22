# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

from constants import LDIF_PARSER_IGNORED_ATTRIBUTES
from operations import OPERATIONS
from parser import Parser
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def apply_ldif(ldif_file: str | Path, target_database: str):
    with open(ldif_file, "rt") as f:
        parser = Parser(f, ignored_attr_types=LDIF_PARSER_IGNORED_ATTRIBUTES)
        parser.parse()

    engine = create_engine(target_database)
    with Session(engine) as session:
        for record in parser.all_records:
            operation = OPERATIONS[record.model]
            operation.get_registry(record.op)(operation(), session, record)
        session.commit()
