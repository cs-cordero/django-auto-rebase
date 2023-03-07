import argparse
import inspect
import os
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Tuple

import django
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.loader import MigrationLoader

if sys.version_info < (3, 9):
    from typing import Iterable
else:
    from collections.abc import Iterable


class MigrationTuple(NamedTuple):
    app_label: str
    name: str


def main() -> None:
    args = get_arguments()
    set_pythonpath()
    django.setup()

    loader = MigrationLoader(connection=None)
    leaf_nodes = filter_migrations(args.app, loader.graph.leaf_nodes())
    if len(leaf_nodes) < 2:
        print("No migrations to rebase")
        sys.exit(0)
    elif len(leaf_nodes) > 2:
        sys.exit("Too many leaf nodes")
    assert len(leaf_nodes) == 2
    remote_migration = MigrationTuple(args.app, args.migration)
    leaf_nodes.remove(remote_migration)
    local_migration = leaf_nodes[0]

    base_migrations, migrations_to_rebase = find_migrations_to_rebase(
        loader.graph, local_migration, remote_migration
    )
    if not base_migrations:
        sys.exit("The given migrations don't have a common base")
    assert len(base_migrations) == 1
    base_migration = base_migrations[0]
    head_migration = local_migration
    for migration in migrations_to_rebase:
        migration_class = loader.get_migration(*migration)
        migration_path = Path(inspect.getfile(migration_class.__class__))
        new_migration_name = get_new_migration_name(head_migration.name, migration.name)
        new_path = migration_path.parent / f"{new_migration_name}.py"

        original_contents = migration_path.read_text()

        dependencies_pattern = re.compile(
            rf"""
            (
                (['"])
                {base_migration.app_label}
                \2
                ,
                \s*
                (['"])
            )
            {base_migration.name}
            \3
            """,
            re.MULTILINE | re.VERBOSE,
        )
        new_contents = dependencies_pattern.sub(
            rf"\g<1>{head_migration.name}\g<3>", original_contents
        )

        migration_path.rename(new_path)
        new_path.write_text(new_contents)

        run_black_if_available(new_path)
        base_migration = migration
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
    graph: MigrationGraph,
    local_migration: MigrationTuple,
    remote_migration: MigrationTuple,
) -> Tuple[List[MigrationTuple], List[MigrationTuple]]:
    assert local_migration.app_label == remote_migration.app_label
    app = remote_migration.app_label
    local_plan = filter_migrations(app, graph.forwards_plan(local_migration))
    remote_plan = filter_migrations(app, graph.forwards_plan(remote_migration))
    for i, (lm, rm) in enumerate(zip(local_plan, remote_plan)):
        if lm != rm:
            return (remote_plan[i - 1 : i], remote_plan[i:])
    return (
        remote_plan[len(local_plan) - 1 : len(local_plan)],
        remote_plan[len(local_plan) :],
    )


def filter_migrations(
    app_label: str, migrations: Iterable[Tuple[str, str]]
) -> List[MigrationTuple]:
    return [MigrationTuple(app, name) for app, name in migrations if app == app_label]


def get_new_migration_name(base_name: str, original_name: str) -> str:
    _, _, original = original_name.partition("_")
    base_magic_number, _, _ = base_name.partition("_")
    new_magic_number = str(int(base_magic_number) + 1).zfill(4)
    return f"{new_magic_number}_{original}"


def run_black_if_available(filepath: Path) -> None:
    try:
        import black  # type: ignore # noqa: F401

        os.system(f"black {filepath}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
