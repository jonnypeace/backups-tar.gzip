#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated
from functools import cached_property

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

INCREMENTAL_FILENAME = "backup.inc"


class ConfigNotFoundError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass


class BackupError(Exception):
    pass


class RestoreError(Exception):
    pass


class FileDirectoryRenameError(Exception):
    pass


DATE_TIME_FORMAT = "%Y.%m.%d.%H.%M.%S"
REGEX = re.compile(r"(\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2})")


def now_time() -> str:
    """
    Returns the date using system time YYYY.MM.DD.HH.MM.SS
    """
    return datetime.now().astimezone().strftime(DATE_TIME_FORMAT)


def parse_timestamp(file: str) -> tuple[int, int, int, int, int, int]:
    """
    Parse filename strings which were created by backup.py

    Returns a tuple with year, month, day, hours, mins, secs.
    """
    found = REGEX.search(file)
    if not found:
        raise FileDirectoryRenameError(
            f"File or folder names do not have correct datetime format in path name:\n{file}"
        )
    y, m, d, h, mi, s = (int(x) for x in found.group(1).split("."))
    return (y, m, d, h, mi, s)


ProjectName = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z][\w-]*$")]


def _abs_path(v: Path) -> Path:
    """
    This is for encorcing absolute paths in pydantic
    """
    if not v.is_absolute():
        raise ValueError(f"paths must be absolute, got '{v}'")
    return v


AbsPath = Annotated[Path, AfterValidator(_abs_path)]


class Retention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    consolidate_after: int = 7
    keep_archives: int = 3


class Defaults(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    destination: AbsPath = Path.home() / "backups"
    excludes: list[str] = Field(default_factory=list)
    retention: Retention = Field(default_factory=Retention)
    compress: bool = True


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: AbsPath | None = None
    destination: AbsPath | None = None
    retention: Retention | None = None
    compress: bool | None = None
    includes: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)
    backup_filename: str

    @model_validator(mode="after")
    def _source_xor_includes(self) -> Project:
        if self.source and self.includes:
            raise ValueError("use source OR includes, not both")
        if self.source is None and not self.includes:
            raise ValueError("project needs a source directory or an includes list")
        return self

    @model_validator(mode="after")
    def _file_extension(self) -> Project:
        name = self.backup_filename
        regex = re.compile(r"[\\/]+")
        if name.endswith((".tar", ".tar.gz", ".tgz")) or regex.findall(name):
            raise ValueError(
                "backup_filename should have no extension; it is added automatically"
            )
        return self


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    defaults: Defaults
    projects: dict[ProjectName, Project]


def _check_not_recursive(source: Path, destination: Path) -> None:
    """
    This is to ensure the archives don't archive themselves.
    """
    source = source.resolve()
    destination = destination.resolve()
    # True when destination == source OR destination is nested inside source
    if destination.is_relative_to(source):
        raise ValueError(
            f"destination {destination} is inside source {source}; "
            "the backup would archive itself"
        )


def update_project(config: Config, name: str) -> Project:
    """
    Apply project entries against default entries.

    Returns:
        Project
    """

    project = config.projects[name].model_copy()
    d = config.defaults
    if project.destination is None:
        project.destination = d.destination
    if project.retention is None:
        project.retention = d.retention
    if project.compress is None:
        project.compress = d.compress

    project.excludes = project.excludes + d.excludes
    if project.source:
        _check_not_recursive(source=project.source, destination=project.destination)
    for dir in project.includes:
        _check_not_recursive(source=Path(dir), destination=project.destination)

    return project


class Args(BaseModel):
    config: Path
    backup: bool
    restore: list[Path] | None = None
    project_name: str

    @model_validator(mode="after")
    def check_args(self) -> Args:
        if self.backup and self.restore:
            msg = "Need to run either --backup or --restore. Not both at the same time"
            raise ValidationError(msg)

        if self.backup is False and not self.restore:
            msg = "Need at least --backup or --restore"
            raise ValidationError(msg)

        return self


class ParseArgs:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog="backup.py",
            description="Back Up utility for incremental Tar Backups - Space Saving backups!",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        self.parser.add_argument(
            "--config", "-c", type=Path, metavar="YAML_FILE_PATH", required=True
        )

        self.parser.add_argument(
            "--project", "-p", type=str, metavar="PROJECT_NAME", required=True
        )

        self.parser.add_argument("--backup", "-b", action="store_true", default=False)

        self.parser.add_argument(
            "--restore",
            "-r",
            nargs=2,
            type=Path,
            metavar=("RESTORE_FROM", "RESTORE_TO"),
        )
        self.args = self.parser.parse_args()
        self.config_validate()

    def config_validate(self):
        if not self.args.config.exists():
            msg = f"Error: Config does not exist: {self.args.config}"
            raise ConfigNotFoundError(msg)
        if not self.args.config.is_file():
            msg = f"Config Cannot be a directory: {self.args.config}"
            raise ConfigNotFoundError(msg)

    def get_args(self):
        return Args(
            config=self.args.config,
            backup=self.args.backup,
            restore=self.args.restore,
            project_name=self.args.project,
        )


def get_project(args: Args, config: Config) -> Project:
    for key in config.projects:
        if args.project_name == key:
            project = update_project(config=config, name=key)
            return project

    project_names = list(config.projects.keys())

    msg = "No project_name matched --project or project_name in yaml"
    print("--project:", args.project_name)
    print("\nProject List:")
    print("  -", "\n  - ".join(project_names))
    raise ProjectNotFoundError(msg)


class TarIncremental:
    def __init__(self, args: Args, project: Project):
        """
        This is for the incremental backup functionality.

        Args:
            args: Args
            project: Project

        Attributes:
            youngest_dir: Path (This is for storing the youngest directory)
            oldest_dir: Path (This is for storing the oldest directory)
            tmp_list: list[str] (Stores temporary files for deletion at the end)
        """
        self.args = args
        self.project = project
        self.youngest_dir: Path
        self.oldest_dir: Path
        self.tmp_list: list[str] = []
        if self.project.destination is not None:
            self.project.destination.mkdir(exist_ok=True, parents=True)

    def rotate_dirs(self):
        if self.project.destination is None:
            raise AttributeError("Destination needs to be included in yaml")
        self.youngest_dir = (
            self.project.destination / f"{self.args.project_name}-{self.now}"
        )
        self.youngest_dir.mkdir(parents=True, exist_ok=True)

    def _get_dirs(self, prefix: str) -> list[Path]:
        assert self.project.destination is not None
        directories = [
            d
            for d in self.project.destination.iterdir()
            if d.is_dir() and d.name.startswith(prefix)
        ]
        return directories

    @cached_property
    def now(self) -> str:
        now = now_time()
        return now

    def handle_dir_structure(self):
        if self.project.destination is not None and self.project.retention is not None:
            prefix = self.args.project_name + "-"
            directories: list[Path] = self._get_dirs(prefix=prefix)
            if not directories:
                self.rotate_dirs()
                directories = self._get_dirs(prefix=prefix)

            self.oldest_dir = min(directories, key=lambda d: parse_timestamp(d.name))
            self.youngest_dir = max(directories, key=lambda d: parse_timestamp(d.name))
            now = datetime.now().astimezone()
            created = datetime(
                *parse_timestamp(self.oldest_dir.name), tzinfo=now.tzinfo
            )
            if now - created >= timedelta(
                days=self.project.retention.consolidate_after
            ):
                self.rotate_dirs()

            directories = self._get_dirs(prefix=prefix)
            number_of_dirs = len(directories)
            while number_of_dirs > self.project.retention.keep_archives:
                shutil.rmtree(self.oldest_dir)
                number_of_dirs -= 1
                directories = self._get_dirs(prefix=prefix)
                self.oldest_dir = min(
                    directories, key=lambda d: parse_timestamp(d.name)
                )

    def temp_file(self, data: list[str]):
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write("\n".join(data))
            tmp.flush()
            tmp.seek(0)
            tmp_name = tmp.name
        self.tmp_list.append(tmp.name)
        return tmp_name

    def backup_tar_args(self) -> list:
        args = ["-vcz"] if self.project.compress else ["-vc"]
        backup_filename = (
            f"{self.project.backup_filename}-{self.now}.tar.gz"
            if self.project.compress
            else f"{self.project.backup_filename}-{self.now}.tar"
        )
        args += [
            "-g",
            str(self.youngest_dir / INCREMENTAL_FILENAME),
            "-f",
            str(self.youngest_dir / backup_filename),
        ]

        if self.project.includes:
            args += ["-T", self.temp_file(self.project.includes)]
        else:
            args += [str(self.project.source)]

        if self.project.excludes:
            args = ["-X", self.temp_file(self.project.excludes)] + args

        return ["tar"] + args

    def backup(self):
        try:
            self.handle_dir_structure()
            args = self.backup_tar_args()

            proc = subprocess.run(
                args=args, capture_output=True, text=True, check=False
            )
            if proc.stdout:
                print(proc.stdout)
            if proc.returncode >= 2:
                raise BackupError(proc.stderr)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
        finally:
            for tmp_file in self.tmp_list:
                os.remove(tmp_file)

    def restore(self):
        if self.args.restore is None:
            msg = "No restore command has been invoked with paths from -> to"
            raise RestoreError(msg)
        restore_from = self.args.restore[0]
        if not restore_from.exists() or restore_from.is_file():
            raise RestoreError(
                f"Restore From does not exist or is a file: {restore_from}"
            )
        restore_to = self.args.restore[1]
        restore_to.mkdir(parents=True, exist_ok=True)
        files = {*restore_from.rglob("*.tar"), *restore_from.rglob("*tar.gz")}
        files = sorted(files, key=lambda p: parse_timestamp(p.name))
        for file in files:
            args = [
                "tar",
                "-vx",
                "-g",
                "/dev/null",
                "-f",
                str(file),
                "-C",
                str(restore_to),
            ]
            proc = subprocess.run(
                args=args, capture_output=True, text=True, check=False
            )
            if proc.stdout:
                print(proc.stdout)
            if proc.returncode >= 2:
                raise RestoreError(proc.stderr)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)


def main():
    args: Args = ParseArgs().get_args()
    with open(args.config, encoding="utf-8") as file:
        config = Config.model_validate(yaml.safe_load(file))
    project = get_project(args, config)
    tar = TarIncremental(args, project)
    if args.backup:
        tar.backup()
    if args.restore:
        tar.restore()


if __name__ == "__main__":
    try:
        main()
    except (
        ConfigNotFoundError,
        ProjectNotFoundError,
        BackupError,
        RestoreError,
        ValidationError,
        yaml.YAMLError,
        FileDirectoryRenameError,
    ) as e:
        print(f"error: {e}", file=sys.stderr)
