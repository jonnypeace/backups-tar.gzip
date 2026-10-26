from pathlib import Path

import pytest

from backups_tar_gzip.backup import (
    Config,
    FileDirectoryRenameError,
    Project,
    Retention,
    parse_timestamp,
    update_project,
)

# parse_timestamp

def test_parse_timestamp_valid() -> None:
    assert parse_timestamp("test_project-2026.10.26.20.30.59") == (
        2026, 10, 26, 20, 30, 59,
    )


def test_parse_timestamp_ignores_surrounding_text() -> None:
    # REGEX.search, so the timestamp can be embedded anywhere
    assert parse_timestamp("backup-2026.01.02.03.04.05.tar.gz") == (
        2026, 1, 2, 3, 4, 5,
    )


def test_parse_timestamp_missing_raises() -> None:
    with pytest.raises(FileDirectoryRenameError):
        parse_timestamp("test_project-no-timestamp-here")


def test_parse_timestamp_zero_padded() -> None:
    assert parse_timestamp("x-2026.01.01.00.00.00") == (2026, 1, 1, 0, 0, 0)


# update_project

def make_config(tmp_path: Path, **project_kwargs: object) -> Config:
    project_kwargs.setdefault("source", tmp_path / "src")
    config: Config = Config.model_validate(
        {
            "defaults": {
                "destination": str(tmp_path / "backups"),
                "retention": {"consolidate_after": 5, "keep_archives": 2},
                "compress": False,
                "excludes": ["default_exclude"],
            },
            "projects": {
                "proj": {
                    "backup_filename": "proj_backup",
                    **project_kwargs,
                },
            },
        }
    )
    return config


def test_update_project_applies_defaults(tmp_path: Path) -> None:
    config: Config = make_config(tmp_path)
    project: Project = update_project(config, "proj")
    assert project.destination == tmp_path / "backups"
    assert project.retention == Retention(
        consolidate_after=5, keep_archives=2
    )
    assert project.compress is False


def test_update_project_overrides_win(tmp_path: Path) -> None:
    config: Config = make_config(
        tmp_path,
        destination=str(tmp_path / "elsewhere"),
        retention={"consolidate_after": 99, "keep_archives": 99},
        compress=True,
    )
    project: Project = update_project(config, "proj")
    assert project.destination == tmp_path / "elsewhere"
    assert project.retention == Retention(
        consolidate_after=99, keep_archives=99
    )
    assert project.compress is True


def test_update_project_merges_excludes(tmp_path: Path) -> None:
    config: Config = make_config(tmp_path, excludes=["proj_exclude"])
    project: Project = update_project(config, "proj")
    # project excludes first, then defaults
    assert project.excludes == ["proj_exclude", "default_exclude"]


def test_update_project_rejects_destination_inside_source(
    tmp_path: Path,
) -> None:
    config: Config = make_config(
        tmp_path,
        source=str(tmp_path / "src"),
        destination=str(tmp_path / "src" / "nested"),
    )
    with pytest.raises(ValueError, match="inside source"):
        update_project(config, "proj")


def test_update_project_rejects_destination_equal_to_source(
    tmp_path: Path,
) -> None:
    config: Config = make_config(
        tmp_path,
        source=str(tmp_path / "src"),
        destination=str(tmp_path / "src"),
    )
    with pytest.raises(ValueError, match="inside source"):
        update_project(config, "proj")


def test_update_project_allows_destination_outside_source(
    tmp_path: Path,
) -> None:
    config: Config = make_config(tmp_path, destination=str(tmp_path / "dest"))
    project: Project = update_project(config, "proj")
    assert project.destination == tmp_path / "dest"


def test_update_project_includes_list(tmp_path: Path) -> None:
    config: Config = make_config(
        tmp_path,
        source=None,
        includes=[str(tmp_path / "a"), str(tmp_path / "b")],
    )
    project: Project = update_project(config, "proj")
    assert project.includes == [str(tmp_path / "a"), str(tmp_path / "b")]