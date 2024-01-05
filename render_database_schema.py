#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Iterable, Type

from sqlalchemy_data_model_visualizer import generate_data_model_diagram

from src.database import Base, Group, IncludeGroup, User


def main(database_models: Iterable[Type[Base]], output_file_path: str):
    generate_data_model_diagram(database_models, output_file_path)


if __name__ == "__main__":
    models = [User, Group, IncludeGroup]
    output_file = "img/database_schema_diagram"
    main(models, output_file)
