import shutil
import subprocess
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import CompletedProcess

import pytest

CONFIG_PATH = Path(__file__).parent / "config.yaml"
SOURCE_DIR = Path("/tmp/backup_test_source")
DEST_DIR = Path("/tmp/backup_test_dest")
RESTORE_DIR = Path("/tmp/backup_test_restore")
SCRIPT_PATH = Path(__file__).parent.parent / "src" / "backups_tar_gzip" / "backup.py"
PYTHON = Path(__file__).parent.parent / ".venv" / "bin" / "python"


@pytest.fixture(scope="module", autouse=True)
def setup_test_env() -> Generator[None]:
    for path in [SOURCE_DIR, DEST_DIR, RESTORE_DIR]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    yield
    for path in [SOURCE_DIR, DEST_DIR, RESTORE_DIR]:
        if path.exists():
            shutil.rmtree(path)


def run_app(*args: str) -> CompletedProcess[str]:
    assert SCRIPT_PATH.exists(), f"script not found: {SCRIPT_PATH}"
    assert PYTHON.exists(), f"interpreter not found: {PYTHON}"
    return subprocess.run(
        [str(PYTHON), "-u", str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def stamp(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y.%m.%d.%H.%M.%S")


def test_backup_and_restore_flow():
    (SOURCE_DIR / "file1.txt").write_text("content1")
    (SOURCE_DIR / "file2.txt").write_text("content2")

    # Mock 3 weeks of existing incremental backups
    oldest = DEST_DIR / f"test_project-{stamp(21)}"
    middle = DEST_DIR / f"test_project-{stamp(14)}"
    youngest = DEST_DIR / f"test_project-{stamp(7)}"
    for d in (oldest, middle, youngest):
        d.mkdir(parents=True, exist_ok=True)

    result = run_app(
        "--config", str(CONFIG_PATH),
        "--project", "test_project",
        "--backup",
    )
    assert result.returncode == 0, f"backup failed:\n{result.stderr}"

    # Rotation: oldest pruned, others kept, new dir created
    assert not oldest.exists(), "oldest dir should have been rotated away"
    assert middle.exists() and youngest.exists()
    dirs = [d for d in DEST_DIR.iterdir()
            if d.is_dir() and d.name.startswith("test_project-")]
    assert len(dirs) == 3

    archives = sorted(DEST_DIR.rglob("test_backup-*"))
    assert archives, "no backup archive was created"
    listing = subprocess.run(
        ["tar", "-tf", str(archives[-1])],
        capture_output=True, text=True, check=False,
    )
    assert listing.returncode == 0, listing.stderr
    assert "file1.txt" in listing.stdout
    assert "file2.txt" in listing.stdout

    restore_result = run_app(
        "--config", str(CONFIG_PATH),
        "--project", "test_project",
        "--restore", str(archives[-1].parent), str(RESTORE_DIR),
    )
    assert restore_result.returncode == 0, f"restore failed:\n{restore_result.stderr}"

    restored = {p.name: p.read_text() for p in RESTORE_DIR.rglob("file*.txt")}
    assert restored == {"file1.txt": "content1", "file2.txt": "content2"}