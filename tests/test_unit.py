from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from backups_tar_gzip.backup import (
    Args,
    BackupError,
    Config,
    FileDirectoryRenameError,
    Project,
    Retention,
    TarIncremental,
    directory_pattern,
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
        _ = parse_timestamp("test_project-no-timestamp-here")


def test_parse_timestamp_zero_padded() -> None:
    assert parse_timestamp("x-2026.01.01.00.00.00") == (2026, 1, 1, 0, 0, 0)


# update_project

def make_config(tmp_path: Path, **project_kwargs: object) -> Config:
    _ = project_kwargs.setdefault("source", tmp_path / "src")
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
        _ = update_project(config, "proj")


def test_update_project_rejects_destination_equal_to_source(
    tmp_path: Path,
) -> None:
    config: Config = make_config(
        tmp_path,
        source=str(tmp_path / "src"),
        destination=str(tmp_path / "src"),
    )
    with pytest.raises(ValueError, match="inside source"):
        _ = update_project(config, "proj")


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


# Retention bounds

def test_retention_defaults_are_within_the_bounds() -> None:
    retention: Retention = Retention()
    assert retention.consolidate_after == 7
    assert retention.keep_archives == 3


def test_retention_accepts_one_as_the_smallest_allowed_value() -> None:
    retention: Retention = Retention(consolidate_after=1, keep_archives=1)
    assert retention.consolidate_after == 1
    assert retention.keep_archives == 1


@pytest.mark.parametrize("consolidate_after", [0, -1, -7])
def test_retention_rejects_consolidate_after_below_one(consolidate_after: int) -> None:
    with pytest.raises(ValidationError, match="consolidate_after"):
        _ = Retention(consolidate_after=consolidate_after)


@pytest.mark.parametrize("keep_archives", [0, -1, -7])
def test_retention_rejects_keep_archives_below_one(keep_archives: int) -> None:
    with pytest.raises(ValidationError, match="keep_archives"):
        _ = Retention(keep_archives=keep_archives)


def test_config_rejects_out_of_bounds_retention_in_defaults(tmp_path: Path) -> None:
    # The same bounds have to hold for a YAML config, not just direct model use:
    # `keep_archives: 0` used to reach handle_dir_structure() and prune away the
    # backup it had just created.
    with pytest.raises(ValidationError, match="keep_archives"):
        _ = Config.model_validate(
            {
                "defaults": {
                    "destination": str(tmp_path / "backups"),
                    "retention": {"consolidate_after": 7, "keep_archives": 0},
                },
                "projects": {
                    "proj": {
                        "source": str(tmp_path / "src"),
                        "backup_filename": "proj_backup",
                    },
                },
            }
        )


def test_config_rejects_out_of_bounds_retention_in_project_override(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="consolidate_after"):
        _ = Config.model_validate(
            {
                "defaults": {"destination": str(tmp_path / "backups")},
                "projects": {
                    "proj": {
                        "source": str(tmp_path / "src"),
                        "backup_filename": "proj_backup",
                        "retention": {"consolidate_after": 0, "keep_archives": 5},
                    },
                },
            }
        )


# directory_pattern

def stamp(days_ago: int = 0) -> str:
    """A backup directory timestamp `days_ago` days in the past.

    Stamped in UTC; the day-scale gaps used below keep ordering stable even if
    backup.py names directories using local time.
    """
    return (datetime.now(UTC) - timedelta(days=days_ago)).strftime(
        "%Y.%m.%d.%H.%M.%S"
    )


def test_directory_pattern_matches_dirs_backup_creates() -> None:
    assert directory_pattern("docs").fullmatch(f"docs-{stamp()}")


@pytest.mark.parametrize(
    "name",
    [
        "docs",
        "docs-notes",  # a folder a user made by hand
        "docs-backups",
        "notes-docs-2026.10.26.20.30.59",  # timestamp not at the end
        "docs-2026.10.26.20.30.59.old",  # trailing junk
        "docs-2026.10.26.20.30.5",  # seconds truncated
        "docs-2026-10-26-20-30-59",  # backup.sh naming style
    ],
)
def test_directory_pattern_rejects_names_that_are_not_backup_dirs(name: str) -> None:
    assert directory_pattern("docs").fullmatch(name) is None


def test_directory_pattern_does_not_match_another_projects_dirs() -> None:
    # "docs" and "docs-2026" are both valid project names, and the name of one
    # project's backup directory looks a lot like the other project's name.
    docs_dir = "docs-2026.10.26.20.30.59"
    docs_2026_dir = "docs-2026-2026.10.26.20.30.59"

    assert directory_pattern("docs").fullmatch(docs_dir)
    assert directory_pattern("docs").fullmatch(docs_2026_dir) is None

    assert directory_pattern("docs-2026").fullmatch(docs_2026_dir)
    assert directory_pattern("docs-2026").fullmatch(docs_dir) is None


# TarIncremental directory handling

def make_tar(
    tmp_path: Path,
    project_name: str,
    consolidate_after: int = 7,
    keep_archives: int = 3,
    destination: Path | None = None,
) -> TarIncremental:
    destination = destination or tmp_path / "backups"
    args: Args = Args(
        config=tmp_path / "config.yaml",
        backup=True,
        project_name=project_name,
    )
    project: Project = Project(
        backup_filename=f"{project_name}_backup",
        source=tmp_path / "source",
        destination=destination,
        retention=Retention(
            consolidate_after=consolidate_after, keep_archives=keep_archives
        ),
    )
    return TarIncremental(args, project)


def backup_dirs_in(destination: Path, project_name: str) -> list[str]:
    return sorted(
        d.name
        for d in destination.iterdir()
        if d.is_dir() and directory_pattern(project_name).fullmatch(d.name)
    )


def destination_of(tar: TarIncremental) -> Path:
    """Project.destination is optional in the model; these tests always set it."""
    destination: Path | None = tar.project.destination
    assert destination is not None
    return destination


def test_handle_dir_structure_ignores_unrelated_directories(tmp_path: Path) -> None:
    tar: TarIncremental = make_tar(tmp_path, "docs")
    destination: Path = destination_of(tar)

    for days_ago in (21, 14, 7):
        (destination / f"docs-{stamp(days_ago)}").mkdir(parents=True)

    stray: Path = destination / "docs-notes"
    stray.mkdir()
    _ = (stray / "precious.txt").write_text("must survive")

    tar.handle_dir_structure()

    assert stray.is_dir(), "a folder that is not a backup directory was deleted"
    assert (stray / "precious.txt").read_text() == "must survive"
    assert len(backup_dirs_in(destination, "docs")) == 3


def test_handle_dir_structure_keeps_the_newest_dirs(tmp_path: Path) -> None:
    tar: TarIncremental = make_tar(tmp_path, "docs", keep_archives=3)
    destination: Path = destination_of(tar)

    oldest = destination / f"docs-{stamp(21)}"
    middle = destination / f"docs-{stamp(14)}"
    youngest = destination / f"docs-{stamp(7)}"
    for d in (oldest, middle, youngest):
        d.mkdir(parents=True)

    tar.handle_dir_structure()

    assert not oldest.exists(), "oldest backup directory should have been rotated away"
    assert middle.exists() and youngest.exists()
    assert len(backup_dirs_in(destination, "docs")) == 3


def test_handle_dir_structure_does_not_prune_another_projects_dirs(
    tmp_path: Path,
) -> None:
    destination: Path = tmp_path / "backups"

    docs_dirs = [f"docs-{stamp(days_ago)}" for days_ago in (21, 14, 7)]
    docs_2026_dirs = [f"docs-2026-{stamp(days_ago)}" for days_ago in (21, 14)]
    for name in docs_dirs + docs_2026_dirs:
        (destination / name).mkdir(parents=True)

    make_tar(tmp_path, "docs", keep_archives=2, destination=destination).handle_dir_structure()

    surviving = backup_dirs_in(destination, "docs")

    # "docs" pruned its own oldest directories down to keep_archives...
    assert docs_dirs[0] not in surviving
    assert docs_dirs[1] not in surviving
    assert docs_dirs[2] in surviving
    assert len(surviving) == 2

    # ...and pruning them never touched project "docs-2026", whose directory
    # names begin with the name "docs-".
    assert backup_dirs_in(destination, "docs-2026") == docs_2026_dirs


def test_remove_directory_refuses_a_directory_it_did_not_create(tmp_path: Path) -> None:
    tar: TarIncremental = make_tar(tmp_path, "docs")
    destination: Path = destination_of(tar)

    foreign: Path = destination / "docs-notes"
    foreign.mkdir()
    _ = (foreign / "precious.txt").write_text("must survive")

    with pytest.raises(BackupError, match="Refusing to delete"):
        tar._remove_directory(foreign)

    assert foreign.is_dir()
    assert (foreign / "precious.txt").read_text() == "must survive"


def test_remove_directory_refuses_paths_outside_the_destination(tmp_path: Path) -> None:
    tar: TarIncremental = make_tar(tmp_path, "docs")
    destination: Path = destination_of(tar)

    elsewhere: Path = tmp_path / f"docs-{stamp(21)}"
    assert not elsewhere.is_relative_to(destination)
    elsewhere.mkdir()

    with pytest.raises(BackupError, match="Refusing to delete"):
        tar._remove_directory(elsewhere)

    assert elsewhere.is_dir()


def test_remove_directory_deletes_a_real_backup_directory(tmp_path: Path) -> None:
    tar: TarIncremental = make_tar(tmp_path, "docs")
    destination: Path = destination_of(tar)

    backup_dir: Path = destination / f"docs-{stamp(21)}"
    backup_dir.mkdir(parents=True)
    _ = (backup_dir / "archive.tar").write_text("gone")

    tar._remove_directory(backup_dir)

    assert not backup_dir.exists()


# handle_dir_structure at the retention bounds


def test_handle_dir_structure_keeps_the_newest_dir_when_the_bounds_are_one(
    tmp_path: Path,
) -> None:
    # keep_archives: 1 is the smallest value the Retention model allows, and it
    # used to be reachable as a much smaller number. The prune loop must stop at
    # the directory this run has just created instead of deleting it and then
    # asking for the oldest of an empty list.
    tar: TarIncremental = make_tar(
        tmp_path, "docs", consolidate_after=1, keep_archives=1
    )
    destination: Path = destination_of(tar)
    oldest: Path = destination / f"docs-{stamp(21)}"
    oldest.mkdir(parents=True)

    tar.handle_dir_structure()

    surviving: list[str] = backup_dirs_in(destination, "docs")
    assert oldest not in surviving
    assert len(surviving) == 1
    assert surviving[0] == tar.youngest_dir.name


def test_handle_dir_structure_is_a_no_op_for_one_kept_dir_that_is_not_yet_old(
    tmp_path: Path,
) -> None:
    tar: TarIncremental = make_tar(
        tmp_path, "docs", consolidate_after=7, keep_archives=1
    )
    destination: Path = destination_of(tar)
    current: Path = destination / f"docs-{stamp(1)}"
    current.mkdir(parents=True)

    tar.handle_dir_structure()

    assert current.is_dir()
    assert backup_dirs_in(destination, "docs") == [current.name]


def test_handle_dir_structure_with_an_empty_destination_creates_one_dir(
    tmp_path: Path,
) -> None:
    tar: TarIncremental = make_tar(
        tmp_path, "docs", consolidate_after=1, keep_archives=1
    )

    tar.handle_dir_structure()

    assert backup_dirs_in(destination_of(tar), "docs") == [tar.youngest_dir.name]


def test_config_with_keep_archives_one_is_accepted_and_rotates(tmp_path: Path) -> None:
    # A whole config through update_project(), which is what main() does with a
    # YAML file, to show a valid lower bound is not rejected on the way through.
    config: Config = Config.model_validate(
        {
            "defaults": {
                "destination": str(tmp_path / "backups"),
                "retention": {"consolidate_after": 1, "keep_archives": 1},
            },
            "projects": {
                "proj": {
                    "source": str(tmp_path / "src"),
                    "backup_filename": "proj_backup",
                },
            },
        }
    )
    project: Project = update_project(config, "proj")
    assert project.retention == Retention(consolidate_after=1, keep_archives=1)

    args: Args = Args(
        config=tmp_path / "config.yaml", backup=True, project_name="proj"
    )
    tar: TarIncremental = TarIncremental(args, project)
    (destination_of(tar) / f"proj-{stamp(30)}").mkdir(parents=True)

    tar.handle_dir_structure()

    assert len(backup_dirs_in(destination_of(tar), "proj")) == 1