#!/usr/bin/env python3

import os, sys, subprocess, argparse, yaml, tempfile
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class Args:
    config: Path
    backup: bool
    restore: bool
    project_name: str

    def __post_init__(self):
        if all([self.backup, self.restore]):
            print('Need to run either --backup or --restore. Not both at the same time')
            sys.exit(1)

        if all([x is False for x in (self.backup, self.restore)]):
            print('Need at least --backup or --restore')
            sys.exit(1)

@dataclass
class BackUp:
    destination: Path
    source: Path
    includes: list[Path] = field(default_factory=list)
    excludes: list[Path] = field(default_factory=list)

@dataclass
class Restore:
    destination: Path
    source: Path

@dataclass
class Config:
    project_name: str
    backup_filename: str
    backup: BackUp
    restore: Restore

@dataclass
class Projects:
    project: list[Config]

    @classmethod
    def from_yaml(cls, config: Path):
        with open(config) as file:
            data = yaml.safe_load(file)

        project = data.get('projects', [])
        project_list: list[Config] = []

        for conf in project:
            d_backup = conf.get('backup')
            backup = BackUp(
                destination=Path(d_backup["destination"]),
                source=Path(d_backup["source"]),
                includes=list(d_backup.get("includes", [])),
                excludes=list(d_backup.get("excludes", [])),
            )
            d_restore = conf.get('restore')
            restore = Restore(
                destination=Path(d_restore["destination"]),
                source=Path(d_restore["source"])
            )
            c = Config(
                project_name=conf['project_name'],
                backup_filename=conf["backup_filename"],
                backup=backup,
                restore=restore
            )
            project_list.append(c)

        return cls(project=project_list)

class ParseArgs:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog='backup.py',
            description='Back Up utility for incremental Tar Backups - Space Saving backups!',
            formatter_class=argparse.RawTextHelpFormatter
        )
        self.parser.add_argument(
            '--config', '-c',
            nargs=1,
            type=Path,
            metavar='YAML_FILE_PATH',
            default=Path.home() / '.config' / 'pytarinc/' 'config.yaml',
            required=True
        )

        self.parser.add_argument(
            '--project', '-p',
            nargs=1,
            type=str,
            metavar='PROJECT_NAME',
            required=True
        )

        self.parser.add_argument(
            '--backup', '-b',
            action='store_true',
            default=False
        )
        self.parser.add_argument(
            '--restore', '-r',
            action='store_true',
            default=False
        )
        self.args = self.parser.parse_args()
        self.config_validate()

    def config_validate(self):
        if not self.args.config[0].exists():
            print(f'Error: Config does not exist: ', self.args.config[0])
            sys.exit(1)
        if not self.args.config[0].is_file():
            print('Config Cannot be a directory.', self.args.config[0])
            sys.exit(1)

    def get_args(self):
        return Args(
            config=self.args.config[0],
            backup=self.args.backup,
            restore=self.args.restore,
            project_name=self.args.project[0]
            )

def get_config(args: Args, project: Projects)-> Config:
    for x in project.project:
        if args.project_name == x.project_name:
            return x

    print('No project_name matched --project or project_name in yaml')
    print('--project:', args.project_name)
    print('\nProject List:')
    print('  -', '\n  - '.join(x.project_name for x in project.project))
    sys.exit(1)


class TarIncremental:
    def __init__(self, args: Args, config: Config):
        self.args = args
        self.config = config

    def backup(self):
        ...

    def restore(self):
        ...

def main():
    args: Args = ParseArgs().get_args()
    projects: Projects = Projects.from_yaml(args.config)
    config = get_config(args, projects)
    tar = TarIncremental(args, config)
    if args.backup:
        tar.backup()
    if args.restore:
        tar.restore()



if __name__ == '__main__':
    main()