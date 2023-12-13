from pathlib import Path

from constant import LDIF_PARSER_IGNORED_ATTRIBUTES
from operation import OPERATIONS
from parser import Parser
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def apply_ldif(ldif_file: str | Path, dsn: str):
    with open(ldif_file, "rt") as f:
        parser = Parser(f, ignored_attr_types=LDIF_PARSER_IGNORED_ATTRIBUTES)
        parser.parse()

    engine = create_engine(dsn)
    with Session(engine) as session:
        for record in parser.all_records:
            operation_cls = OPERATIONS[record.model]
            operation_cls.get_registry(record.op)(operation_cls(), session, record)
        session.commit()
