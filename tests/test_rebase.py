import os
import shutil
import subprocess
from contextlib import chdir
from pathlib import Path


PROJECT = "testproject"


def test_basic(tmpdir):
    tmpdir = Path(tmpdir)
    src = Path(__file__).parent / PROJECT
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
            )
            and res.returncode > 0
        )

        subprocess.check_call(
            ["dar", "testapp", "0002_reporter_handle"],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "testproject.settings"},
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
        reporter_handle_migration = migrations_dir / "0003_reporter_handle.py"
        assert (
            'dependencies = [("testapp", "0002_alter_reporter_full_name")]'
            in reporter_handle_migration.read_text()
        )

        src_migrations_dir = src / "testapp" / "migrations"
        assert (migrations_dir / "0002_alter_reporter_full_name.py").read_text() == (
            src_migrations_dir / "0002_alter_reporter_full_name.py"
        ).read_text()
