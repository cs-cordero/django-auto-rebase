import os
import re
import sys
from argparse import ArgumentParser
from importlib import import_module
from pathlib import Path
from typing import Any, Dict

import django
from django.apps import apps
from django.db.migrations.loader import MigrationLoader

DEPENDENCIES_PATTERN = re.compile(
    r"(.*?)dependencies.*?=.*?\[.*?\](.*)", re.MULTILINE | re.DOTALL
)


def main() -> None:
    args = get_arguments()
    set_pythonpath()
    django.setup()

    app = apps.get_app_config(args.app)

    migrations = get_leaf_node_migrations_for_app(app)
    original_migration = migrations.pop(args.migration)
    [base_migration_name] = migrations.keys()

    validate_simple_dependencies(original_migration, app.label)

    original_path = Path(original_migration.__file__)
    new_migration_name = get_new_migration_name(base_migration_name, args.migration)
    updated_path = original_path.parent / f"{new_migration_name}.py"

    with original_path.open("r") as f:
        original_contents = f.read()

    match = DEPENDENCIES_PATTERN.match(original_contents)
    assert match is not None, "Regex failed."
    before, after = match.groups()
    middle = f"dependencies = [('{app.label}', '{base_migration_name}')]"

    original_path.rename(updated_path)
    with updated_path.open("w") as f:
        f.write(f"{before}{middle}{after}")

    run_black_if_available(updated_path)


def get_arguments():
    parser = ArgumentParser(
        description="Automatically rebase conflicting Django migrations on top of each other"
    )
    parser.add_argument("app", help="The app_label of the two conflicting migrations")
    parser.add_argument(
        "migration",
        help="The name of the migration that will be rebased on top of the other conflicting migration.",
    )
    return parser.parse_args()


def set_pythonpath():
    path = Path().absolute()
    root = Path(Path().root)
    while path != root and not (path / "manage.py").is_file():
        path = path.parent

    if path == root:
        raise Exception("Could not locate the root of a git project.")

    sys.path.append(str(path))


def get_leaf_node_migrations_for_app(app: Any) -> Dict[str, Any]:
    migration_graph = MigrationLoader(None).graph
    leaf_migrations = {
        migration_name: import_module(f"{app.name}.migrations.{migration_name}")
        for app_name, migration_name in migration_graph.leaf_nodes()
        if app_name == app.label
    }

    if not leaf_migrations:
        raise Exception(f"Found no migrations for app {app.name}.")

    count = len(leaf_migrations)
    if count > 2:
        raise Exception(f"Too many leaf nodes found for app {app.name}! Found {count}.")

    return leaf_migrations


def get_new_migration_name(base_name: str, original_name: str) -> str:
    _, original = original_name.split("_", 1)
    base_magic_number, *_ = base_name.split("_")
    new_magic_number = str(int(base_magic_number) + 1).zfill(4)
    return f"{new_magic_number}_{original}"


def validate_simple_dependencies(migration_module: Any, app_label: str) -> None:
    migration_class = getattr(migration_module, "Migration")
    dependencies = getattr(migration_class, "dependencies", None)
    if dependencies is None:
        raise Exception(
            f"The migration file is missing a `dependencies` attribute for its Migration class."
        )
    if len(dependencies) > 1 or dependencies[0][0] != app_label:
        raise Exception(
            f"Dependency tree is more complicated than usual, you may need to manually edit this one"
        )


def run_black_if_available(filepath: Path) -> None:
    try:
        import black  # type: ignore # noqa: F401

        os.system(f"black {filepath}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
