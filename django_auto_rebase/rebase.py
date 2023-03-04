import argparse
import inspect
import os
import re
import sys
from pathlib import Path
from typing import List, NamedTuple

import django
from django.db.migrations import Migration
from django.db.migrations.loader import MigrationLoader

DEPENDENCIES_PATTERN = re.compile(
    r"(.*?)dependencies.*?=.*?\[.*?\](.*)", re.MULTILINE | re.DOTALL
)


class MigrationTuple(NamedTuple):
    app_label: str
    name: str


def main() -> None:
    args = get_arguments()
    set_pythonpath()
    django.setup()

    loader = MigrationLoader(connection=None)
    leaf_nodes = [
        MigrationTuple(app_label, migration_name)
        for app_label, migration_name in loader.graph.leaf_nodes()
        if app_label == args.app
    ]
    if len(leaf_nodes) < 2:
        print("No migrations to rebase")
        sys.exit(0)
    elif len(leaf_nodes) > 2:
        sys.exit("Too many leaf nodes")
    assert len(leaf_nodes) == 2
    remote_migration = MigrationTuple(args.app, args.migration)
    leaf_nodes.remove(remote_migration)
    local_migration = leaf_nodes[0]

    remote_migration_class = loader.get_migration(*remote_migration)
    validate_simple_dependencies(remote_migration_class)

    migrations_to_rebase = find_migrations_to_rebase(
        loader, local_migration, remote_migration
    )
    head_migration = local_migration
    for migration in migrations_to_rebase:
        migration_class = loader.get_migration(*migration)
        migration_path = Path(inspect.getfile(migration_class.__class__))
        new_migration_name = get_new_migration_name(head_migration.name, migration.name)
        updated_path = migration_path.parent / f"{new_migration_name}.py"

        original_contents = migration_path.read_text()

        match = DEPENDENCIES_PATTERN.match(original_contents)
        if match is None:
            sys.exit(f"Regex failed on {migration.app_label}.{migration.name}")
        before, after = match.groups()
        middle = (
            f"dependencies = [('{head_migration.app_label}', '{head_migration.name}')]"
        )

        migration_path.rename(updated_path)
        updated_path.write_text(f"{before}{middle}{after}")

        run_black_if_available(updated_path)
        head_migration = migration._replace(name=new_migration_name)


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatically rebase conflicting Django migrations on top of each other"
    )
    parser.add_argument("app", help="The app_label of the two conflicting migrations")
    parser.add_argument(
        "migration",
        help="The name of the migration that will be rebased on top of the other conflicting migration.",
    )
    return parser.parse_args()


def set_pythonpath() -> None:
    path = Path().absolute()
    root = Path(Path().root)
    while path != root and not (path / "manage.py").is_file():
        path = path.parent

    if path == root:
        raise Exception("Could not locate the root of a git project.")

    sys.path.append(str(path))


def find_migrations_to_rebase(
    loader: MigrationLoader,
    local_migration: MigrationTuple,
    remote_migration: MigrationTuple,
) -> List[MigrationTuple]:
    local_plan = loader.graph.forwards_plan(local_migration)
    remote_plan = loader.graph.forwards_plan(remote_migration)
    for i, (lm, rm) in enumerate(zip(local_plan, remote_plan)):
        if lm != rm:
            return list(map(MigrationTuple._make, remote_plan[i:]))
    return list(map(MigrationTuple._make, remote_plan[len(local_plan) :]))


def get_new_migration_name(base_name: str, original_name: str) -> str:
    _, _, original = original_name.partition("_")
    base_magic_number, _, _ = base_name.partition("_")
    new_magic_number = str(int(base_magic_number) + 1).zfill(4)
    return f"{new_magic_number}_{original}"


def validate_simple_dependencies(migration: Migration) -> None:
    dependencies = getattr(migration, "dependencies", None)
    if dependencies is None:
        raise Exception(
            f"The migration file is missing a `dependencies` attribute for its Migration class."
        )
    if len(dependencies) > 1 or dependencies[0][0] != migration.app_label:
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
