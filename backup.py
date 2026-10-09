#!/usr/bin/env python3

import argparse
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class GetFileTimeDelta:
    def __init__(self) -> None:
        self.os_name = platform.system()
        self.stat_map: dict = {
            "Windows": self.win_stat,
            "Linux": self.linux_stat,
            "Darwin": self.mac_stat,
        }

    def win_stat(self, file: Path) -> float:
        return os.stat(file).st_ctime

    def linux_stat(self, file: Path) -> float | None:
        args: list = ["stat", "-c", "%W", str(file)]
        proc = subprocess.run(args=args, capture_output=True, text=True, check=True)
        if proc.stdout:
            return float(proc.stdout)
        if proc.stderr:
            raise RuntimeError(proc.stderr)

    def mac_stat(self, file: Path) -> float:
        return os.stat(file).st_birthtime  # type: ignore Not available on linux

    def calculate_timedelta(self, file: Path) -> int:
        stat_func = self.stat_map.get(self.os_name)
        now = time.time()
        if stat_func is not None:
            file_time = stat_func(file)
        else:
            file_time = os.stat(file).st_ctime
        return math.floor((now - file_time) / 60 / 24)


ProjectName = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z][\w-]*$")]


class Retention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    consolidate_after: int = 7
    keep_archives: int = 3


class Defaults(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    destination: Path = Path.home() / "backups"
    excludes: list[str] = Field(default_factory=list)
    retention: Retention = Field(default_factory=Retention)
    compress: bool = True
    incremental_filename: str = "backup.inc"


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Path | None = None
    destination: Path | None = None
    retention: Retention | None = None
    compress: bool | None = None
    includes: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)
    incremental_filename: str | None = None
    backup_filename: str

    @model_validator(mode="after")
    def _source_xor_includes(self) -> Project:
        if self.source and self.includes:
            raise ValueError("use source OR includes, not both")
        if self.source is None and not self.includes:
            raise ValueError("project needs a source directory or an includes list")
        return self


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    defaults: Defaults
    projects: dict[ProjectName, Project]


def update_project(config: Config, name: str) -> Project:
    project = config.projects[name].model_copy()
    d = config.defaults
    if project.destination is None:
        project.destination = d.destination
    if project.retention is None:
        project.retention = d.retention
    if project.compress is None:
        project.compress = d.compress
    if project.incremental_filename is None:
        project.incremental_filename = d.incremental_filename

    project.excludes = project.excludes + d.excludes
    return project


class Args(BaseModel):
    config: Path
    backup: bool
    restore: list[Path] | None = None
    project_name: str

    @model_validator(mode="after")
    def check_args(self) -> Args:
        if all([self.backup, self.restore]):
            print("Need to run either --backup or --restore. Not both at the same time")
            sys.exit(1)

        if all(x is False for x in (self.backup, self.restore)):
            print("Need at least --backup or --restore")
            sys.exit(1)

        return self


class ParseArgs:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog="backup.py",
            description="Back Up utility for incremental Tar Backups - Space Saving backups!",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        self.parser.add_argument(
            "--config",
            "-c",
            nargs=1,
            type=Path,
            metavar="YAML_FILE_PATH",
            default=Path.home() / ".config" / "pytar/config.yaml",
            required=True,
        )

        self.parser.add_argument(
            "--project", "-p", nargs=1, type=str, metavar="PROJECT_NAME", required=True
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
        if not self.args.config[0].exists():
            print("Error: Config does not exist: ", self.args.config[0])
            sys.exit(1)
        if not self.args.config[0].is_file():
            print("Config Cannot be a directory.", self.args.config[0])
            sys.exit(1)

    def get_args(self):
        return Args(
            config=self.args.config[0],
            backup=self.args.backup,
            restore=self.args.restore,
            project_name=self.args.project[0],
        )


def get_project(args: Args, config: Config) -> Project:
    project_names: list = []
    for key in config.projects:
        if args.project_name == key:
            project = update_project(config=config, name=key)
            return project
        project_names.append(key)

    print("No project_name matched --project or project_name in yaml")
    print("--project:", args.project_name)
    print("\nProject List:")
    print("  -", "\n  - ".join(project_names))
    sys.exit(1)


class TarIncremental:
    def __init__(self, args: Args, project: Project):
        self.args = args
        self.project = project
        self.time_delta = GetFileTimeDelta()
        self.min_dir: Path
        self.max_dir: Path
        self.tmp_list: list[str] = []
        if self.project.destination is not None:
            self.project.destination.mkdir(exist_ok=True, parents=True)

    def rotate_dirs(self):
        now = datetime.now(ZoneInfo("Europe/London")).strftime("%d.%m.%Y.%H.%M.%S")
        if self.project.destination is None:
            raise AttributeError("Destination needs to be included in yaml")
        self.min_dir = self.project.destination / f"{self.args.project_name}-{now}"
        self.min_dir.mkdir(parents=True, exist_ok=True)

    def get_min_dir(
        self, directories_delta: list[tuple[Path, int]]
    ) -> tuple[Path, int]:
        return min(directories_delta, key=lambda pair: pair[1])

    def get_max_dir(
        self, directories_delta: list[tuple[Path, int]]
    ) -> tuple[Path, int]:
        return max(directories_delta, key=lambda pair: pair[1])

    def handle_dir_structure(self):
        if self.project.destination is not None and self.project.retention is not None:
            directories = list(Path(self.project.destination).iterdir())
            if not directories:
                self.rotate_dirs()
                self.handle_dir_structure()
            count = sum(1 for x in directories for p in x.iterdir() if p.is_file())
            if count >= 1:
                directories_delta: list[tuple[Path, int]] = [
                    (x, self.time_delta.calculate_timedelta(x)) for x in directories
                ]
                self.min_dir, min_int = self.get_min_dir(directories_delta)
                self.max_dir, _ = self.get_max_dir(directories_delta)
            else:
                self.rotate_dirs()  # Start fresh
                min_int = 0

            if min_int >= self.project.retention.consolidate_after:
                self.rotate_dirs()

            if len(directories) >= self.project.retention.keep_archives:
                shutil.rmtree(self.max_dir)

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
        assert self.project.incremental_filename is not None
        backup_filename = (
            f"{Path(self.project.backup_filename)}.tar.gz"
            if self.project.compress
            else f"{Path(self.project.backup_filename)}.tar"
        )
        args += [
            "-g",
            str(self.min_dir / self.project.incremental_filename),
            "-f",
            str(self.min_dir / backup_filename),
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

            proc = subprocess.run(args=args, capture_output=True, text=True, check=True)
            if proc.stdout:
                print(proc.stdout)
            if proc.stderr:
                print(proc.stderr)
                sys.exit(1)
        finally:
            for tmp_file in self.tmp_list:
                os.remove(tmp_file)

    def restore(self):
        if self.args.restore is None:
            print("No restore command has been invoked with paths from -> to")
            sys.exit(1)
        restore_from = self.args.restore[0]
        restore_to = self.args.restore[1]
        restore_to.mkdir(parents=True, exist_ok=True)
        files = {*restore_from.rglob("*.tar"), *restore_from.rglob("*tar.gz")}
        files = sorted(files, key=lambda x: x.stat().st_mtime)
        args = ["tar", "-vx", "-g", "/dev/null", "-f", restore_to]
        for file in files:
            proc = subprocess.run(args=args, capture_output=True, text=True, check=True)
            if proc.stdout:
                print(proc.stdout)
            if proc.stderr:
                print(proc.stderr)
                sys.exit(1)


def main():
    args: Args = ParseArgs().get_args()
    with open(args.config) as file:
        config = Config.model_validate(yaml.safe_load(file))
    project = get_project(args, config)
    tar = TarIncremental(args, project)
    if args.backup:
        tar.backup()
    if args.restore:
        tar.restore()


if __name__ == "__main__":
    main()
