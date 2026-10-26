import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from subprocess import CompletedProcess

import pytest

CONFIG_TEMPLATE_PATH = Path(__file__).parent / "config.yaml"
SCRIPT_PATH = Path(__file__).parent.parent / "src" / "backups_tar_gzip" / "backup.py"
PYTHON = Path(__file__).parent.parent / ".venv" / "bin" / "python"

SUBPROCESS_TIMEOUT = 60  # seconds


@dataclass(frozen=True)
class Env:
    config_path: Path
    source_dir: Path
    dest_dir: Path
    restore_dir: Path


def write_config(path: Path, source_dir: Path, dest_dir: Path) -> Path:
    """Write a per-test copy of tests/config.yaml with its hardcoded /tmp
    paths repointed at this test's temp dirs, so concurrent runs can't
    clobber each other."""
    text = CONFIG_TEMPLATE_PATH.read_text()
    replacements = {
        "/tmp/backup_test_source": source_dir,
        "/tmp/backup_test_dest": dest_dir,
    }
    for old, new in replacements.items():
        assert old in text, f"{CONFIG_TEMPLATE_PATH} no longer contains {old!r}"
        text = text.replace(old, str(new))
    path.write_text(text)
    return path


@pytest.fixture()
def test_env(tmp_path: Path) -> Env:
    """Function-scoped: every test gets fresh, unique dirs under pytest's
    tmp_path (unique per test and per run); pytest handles cleanup."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    restore_dir = tmp_path / "restore"
    for d in (source_dir, dest_dir, restore_dir):
        d.mkdir()
    config_path = write_config(tmp_path / "config.yaml", source_dir, dest_dir)
    return Env(config_path, source_dir, dest_dir, restore_dir)


def run_app(*args: str) -> CompletedProcess[str]:
    assert SCRIPT_PATH.exists(), f"script not found: {SCRIPT_PATH}"
    assert PYTHON.exists(), f"interpreter not found: {PYTHON}"
    try:
        return subprocess.run(
            [str(PYTHON), "-u", str(SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"backup.py timed out after {SUBPROCESS_TIMEOUT}s: {args}")


def stamp(days_ago: int) -> str:
    # Keep this clock in sync with whatever backup.py uses when naming
    # backup dirs. UTC makes the choice explicit; the day-scale gaps below
    # keep name ordering stable even if the app stamps with local time.
    return (datetime.now(UTC) - timedelta(days=days_ago)).strftime(
        "%Y.%m.%d.%H.%M.%S"
    )


def test_backup_and_restore_flow(test_env: Env) -> None:
    source_dir, dest_dir, restore_dir = (
        test_env.source_dir,
        test_env.dest_dir,
        test_env.restore_dir,
    )

    (source_dir / "file1.txt").write_text("content1")
    (source_dir / "file2.txt").write_text("content2")

    # Mock 3 weeks of existing incremental backups
    oldest = dest_dir / f"test_project-{stamp(21)}"
    middle = dest_dir / f"test_project-{stamp(14)}"
    youngest = dest_dir / f"test_project-{stamp(7)}"
    for d in (oldest, middle, youngest):
        d.mkdir(parents=True, exist_ok=True)

    result = run_app(
        "--config", str(test_env.config_path),
        "--project", "test_project",
        "--backup",
    )
    assert result.returncode == 0, f"backup failed:\n{result.stderr}"

    # Rotation: oldest pruned, others kept, new dir created
    assert not oldest.exists(), "oldest dir should have been rotated away"
    assert middle.exists() and youngest.exists()
    dirs = [d for d in dest_dir.iterdir()
            if d.is_dir() and d.name.startswith("test_project-")]
    assert len(dirs) == 3

    archives = sorted(dest_dir.rglob("test_backup-*"))
    assert archives, "no backup archive was created"
    listing = subprocess.run(
        ["tar", "-tf", str(archives[-1])],
        capture_output=True, text=True, check=False,
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert listing.returncode == 0, listing.stderr
    assert "file1.txt" in listing.stdout
    assert "file2.txt" in listing.stdout

    restore_result = run_app(
        "--config", str(test_env.config_path),
        "--project", "test_project",
        "--restore", str(archives[-1].parent), str(restore_dir),
    )
    assert restore_result.returncode == 0, f"restore failed:\n{restore_result.stderr}"

    restored = {p.name: p.read_text() for p in restore_dir.rglob("file*.txt")}
    assert restored == {"file1.txt": "content1", "file2.txt": "content2"}