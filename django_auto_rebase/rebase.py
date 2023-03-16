import argparse
import inspect
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

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

    def __str__(self):
        return f"{self.app_label}.{self.name}"


def main() -> None:
    args = get_arguments()

    manage_py_path = find_manage_py()
    if manage_py_path is None:
        sys.exit("Could not locate manage.py")
    sys.path.append(str(manage_py_path.parent))
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        settings_module = guess_settings_module(manage_py_path)
        if settings_module:
            os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    django.setup()

    loader = MigrationLoader(connection=None)
    remote = MigrationTuple(args.app, args.migration)
    if remote not in loader.graph.nodes:
        sys.exit(f"Migration {remote} doesn't exist")
    leaf_nodes = filter_migrations(args.app, loader.graph.leaf_nodes())
    if len(leaf_nodes) < 2:
        print("No migrations to rebase")
        sys.exit(0)
    elif len(leaf_nodes) > 2:
        sys.exit("Too many leaf nodes")
    assert len(leaf_nodes) == 2
    try:
        leaf_nodes.remove(remote)
    except ValueError:
        print(
            f"Migration {remote} is not a leaf node. Possible rebase candidates:",
            file=sys.stderr,
        )
        for node in sorted(leaf_nodes):
            print(f"- {node}", file=sys.stderr)
        sys.exit(1)
    local = leaf_nodes[0]

    bases, migrations_to_rebase = find_migrations_to_rebase(loader.graph, local, remote)
    if not bases:
        sys.exit("The given migrations don't have a common base")
    assert len(bases) == 1
    base = bases[0]
    head = local
    for migration in migrations_to_rebase:
        print(f"Rebasing {migration}")
        migration_obj = loader.get_migration(*migration)
        migration_path = Path(inspect.getfile(migration_obj.__class__))
        new_name = get_new_migration_name(head.name, migration.name)
        new_path = migration_path.parent / f"{new_name}.py"

        orig_contents = migration_path.read_text()
        dependencies_pattern = re.compile(
            rf"""
            (
                (['"])
                {base.app_label}
                \2
                ,
                \s*
                (['"])
            )
            {base.name}
            \3
            """,
            re.MULTILINE | re.VERBOSE,
        )
        new_contents = dependencies_pattern.sub(rf"\g<1>{head.name}\3", orig_contents)

        migration_path.rename(new_path)
        new_path.write_text(new_contents)

        run_black_if_available(new_path)

        base = migration
        head = migration._replace(name=new_name)


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatically rebase conflicting Django migrations on top of each other."
    )
    parser.add_argument("app", help="the app_label of the two conflicting migrations")
    parser.add_argument(
        "migration",
        help="the name of the migration that will be rebased on top of the other conflicting migration",
    )
    return parser.parse_args()


def find_manage_py() -> Optional[Path]:
    path = Path("manage.py").absolute()
    for parent in path.parents:
        path = parent / "manage.py"
        if path.is_file():
            return path
    return None


def guess_settings_module(manage_py_path: Path) -> Optional[str]:
    manage_py_contents = manage_py_path.read_text()
    mo = re.search(
        r"""
        environ\.setdefault\(
            ['"]DJANGO_SETTINGS_MODULE['"],\s*
            ['"]([^'"]+)['"]
        \)
        """,
        manage_py_contents,
        re.VERBOSE | re.MULTILINE,
    )
    return mo.group(1) if mo else None


def find_migrations_to_rebase(
    graph: MigrationGraph, local: MigrationTuple, remote: MigrationTuple
) -> Tuple[List[MigrationTuple], List[MigrationTuple]]:
    assert local.app_label == remote.app_label
    app_label = remote.app_label
    local_plan = filter_migrations(app_label, graph.forwards_plan(local))
    remote_plan = filter_migrations(app_label, graph.forwards_plan(remote))
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

        subprocess.run(["black", filepath])
    except ImportError:
        pass


if __name__ == "__main__":
    main()
