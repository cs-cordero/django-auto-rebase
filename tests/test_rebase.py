import os
import shutil
import subprocess
from contextlib import AbstractContextManager
from pathlib import Path

import pytest


def test_no_manage_py(tmpdir):
    tmpdir = Path(tmpdir)
    with chdir(tmpdir):
        res = subprocess.run(
            ["dar", "testapp", "0001_initial"],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "testproject.settings"},
            capture_output=True,
            text=True,
        )
        assert (
            res.stderr == "Could not locate manage.py\n"
            and res.stdout == ""
            and res.returncode == 1
        )


@pytest.mark.parametrize(
    "is_settings_module_set",
    [
        pytest.param(True, id="DJANGO_SETTINGS_MODULE is explicitly set"),
        pytest.param(False, id="DJANGO_SETTINGS_MODULE is guessed"),
    ],
)
def test_nothing_to_do(tmpdir, is_settings_module_set):
    tmpdir = Path(tmpdir)
    src = Path(__file__).parent / "testproject_initial"
    shutil.copytree(src, tmpdir, dirs_exist_ok=True)
    with chdir(tmpdir):
        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert (
            res.stderr == ""
            and res.stdout == "No changes detected\n"
            and res.returncode == 0
        )

        res = subprocess.run(
            ["dar", "testapp", "0001_initial"],
            env=(
                {**os.environ, "DJANGO_SETTINGS_MODULE": "testproject.settings"}
                if is_settings_module_set
                else None
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert (
            res.stderr == ""
            and res.stdout == "No migrations to rebase\n"
            and res.returncode == 0
        )


def test_validation(tmpdir):
    tmpdir = Path(tmpdir)
    src = Path(__file__).parent / "testproject_basic"
    shutil.copytree(src, tmpdir, dirs_exist_ok=True)
    with chdir(tmpdir):
        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            capture_output=True,
            text=True,
        )
        assert (
            "Conflicting migrations detected" in res.stderr
            and (
                "(0002_alter_reporter_full_name, 0002_reporter_handle in testapp)"
                in res.stderr
                or "(0002_reporter_handle, 0002_alter_reporter_full_name in testapp)"
                in res.stderr
            )
            and res.returncode > 0
        )

        res = subprocess.run(
            ["dar", "testapp", "9999_unknown_migration"],
            capture_output=True,
            text=True,
        )
        assert (
            res.stderr == "Migration testapp.9999_unknown_migration doesn't exist\n"
            and res.stdout == ""
            and res.returncode == 1
        )

        res = subprocess.run(
            ["dar", "testapp", "0001_initial"],
            capture_output=True,
            text=True,
        )
        assert (
            res.stderr
            == "Migration testapp.0001_initial is not a leaf node. Possible rebase candidates:\n"
            "- testapp.0002_alter_reporter_full_name\n"
            "- testapp.0002_reporter_handle\n"
            and res.returncode == 1
        )


def test_basic(tmpdir):
    tmpdir = Path(tmpdir)
    src = Path(__file__).parent / "testproject_basic"
    shutil.copytree(src, tmpdir, dirs_exist_ok=True)
    with chdir(tmpdir):
        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert (
            "Conflicting migrations detected" in res.stderr
            and (
                "(0002_alter_reporter_full_name, 0002_reporter_handle in testapp)"
                in res.stderr
                or "(0002_reporter_handle, 0002_alter_reporter_full_name in testapp)"
                in res.stderr
            )
            and res.returncode > 0
        )

        res = subprocess.run(
            ["dar", "testapp", "0002_reporter_handle"],
            capture_output=True,
            text=True,
        )
        assert (
            res.stdout == "Rebasing testapp.0002_reporter_handle\n"
            and res.returncode == 0
        )

        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert (
            res.stderr == ""
            and res.stdout == "No changes detected\n"
            and res.returncode == 0
        )

        migrations_dir = tmpdir / "testapp" / "migrations"
        src_migrations_dir = src / "testapp" / "migrations"
        full_name_migration = "0002_alter_reporter_full_name.py"
        assert (migrations_dir / full_name_migration).read_text() == (
            src_migrations_dir / full_name_migration
        ).read_text()

        handle_migration = migrations_dir / "0003_reporter_handle.py"
        assert (
            'dependencies = [("testapp", "0002_alter_reporter_full_name")]'
            in handle_migration.read_text()
        )


def test_multiple_dependencies(tmpdir):
    tmpdir = Path(tmpdir)
    src = Path(__file__).parent / "testproject_basic"
    shutil.copytree(src, tmpdir, dirs_exist_ok=True)
    with chdir(tmpdir):
        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            capture_output=True,
            text=True,
        )
        assert (
            "Conflicting migrations detected" in res.stderr
            and (
                "(0002_alter_reporter_full_name, 0002_reporter_handle in testapp)"
                in res.stderr
                or "(0002_reporter_handle, 0002_alter_reporter_full_name in testapp)"
                in res.stderr
            )
            and res.returncode > 0
        )

        res = subprocess.run(
            ["dar", "testapp", "0002_alter_reporter_full_name"],
            capture_output=True,
            text=True,
        )
        assert (
            res.stdout == "Rebasing testapp.0002_alter_reporter_full_name\n"
            and res.returncode == 0
        )

        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            capture_output=True,
            text=True,
        )
        assert (
            res.stderr == ""
            and res.stdout == "No changes detected\n"
            and res.returncode == 0
        )

        migrations_dir = tmpdir / "testapp" / "migrations"
        src_migrations_dir = src / "testapp" / "migrations"
        full_name_migration = "0002_reporter_handle.py"
        assert (migrations_dir / full_name_migration).read_text() == (
            src_migrations_dir / full_name_migration
        ).read_text()

        handle_migration = migrations_dir / "0003_alter_reporter_full_name.py"
        assert (
            """\
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("testapp", "0002_reporter_handle"),
    ]"""
            in handle_migration.read_text()
        )


def test_multiple_migrations(tmpdir):
    tmpdir = Path(tmpdir)
    src = Path(__file__).parent / "testproject_multiple_migrations"
    shutil.copytree(src, tmpdir, dirs_exist_ok=True)
    with chdir(tmpdir):
        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert (
            "Conflicting migrations detected" in res.stderr
            and (
                "(0002_alter_reporter_full_name, 0003_reporter_level in testapp)"
                in res.stderr
                or "(0003_reporter_level, 0002_alter_reporter_full_name in testapp)"
                in res.stderr
            )
            and res.returncode > 0
        )

        res = subprocess.run(
            ["dar", "testapp", "0003_reporter_level"],
            capture_output=True,
            text=True,
        )
        assert (
            res.stdout == "Rebasing testapp.0002_reporter_handle\n"
            "Rebasing testapp.0003_reporter_level\n"
            and res.returncode == 0
        )

        res = subprocess.run(
            ["python", "manage.py", "makemigrations", "--check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert (
            res.stderr == ""
            and res.stdout == "No changes detected\n"
            and res.returncode == 0
        )

        migrations_dir = tmpdir / "testapp" / "migrations"
        src_migrations_dir = src / "testapp" / "migrations"
        full_name_migration = "0002_alter_reporter_full_name.py"
        assert (migrations_dir / full_name_migration).read_text() == (
            src_migrations_dir / full_name_migration
        ).read_text()

        handle_migration = migrations_dir / "0003_reporter_handle.py"
        assert (
            'dependencies = [("testapp", "0002_alter_reporter_full_name")]'
            in handle_migration.read_text()
        )

        level_migration = migrations_dir / "0004_reporter_level.py"
        assert (
            'dependencies = [("testapp", "0003_reporter_handle")]'
            in level_migration.read_text()
        )


class chdir(AbstractContextManager):
    """Non thread-safe context manager to change the current working directory."""

    def __init__(self, path):
        self.path = path
        self._old_cwd = []

    def __enter__(self):
        self._old_cwd.append(os.getcwd())
        os.chdir(self.path)

    def __exit__(self, *excinfo):
        os.chdir(self._old_cwd.pop())
