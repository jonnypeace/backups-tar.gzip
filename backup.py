#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import yaml
from typing import Annotated, Literal
from pydantic import BaseModel, StringConstraints, Field, model_validator, ConfigDict
import time
import re


# For my future me when i check the backed up files
# FILE = Path("backup.sh")

# TIME_S = os.stat(FILE).st_mtime
# NOW = time.time()

# print((NOW - TIME_S) / 60 / 24)


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


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Path | None = None
    destination: Path | None = None
    retention: Retention | None = None
    compress: bool | None = None
    includes: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)

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

    project.excludes = project.excludes + d.excludes
    return project


class Args(BaseModel):
    config: Path
    backup: bool
    restore: bool
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
        self.parser.add_argument("--restore", "-r", action="store_true", default=False)
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

    def backup(self): ...

    def restore(self): ...


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
