# Incremental Backups using tar and gzip compression

## Backups using TAR

These scripts utilize the tar -g for incremental backups.

Example of full command

```bash
tar -X excludes.txt -vcz -g incremental.file -f backup.tar.gz -T includes.txt
```

When you periodically run this command, subsequent backup file sizes are much smaller.
If you switch backup directories it will start again fresh on the first backup,
then resume smaller backups again.

The recovery is a little more fun. You basically have to loop round the backup
files in order of creation, and restore them somewhere.

The scripts in this repository are used for handling the backup and restore mechanism,
and they are used in conjunction with a yaml configuration, which helps keep things
organised.

## _update: 15-10-2026_

There are two parts to this:

* Bash script (legacy, no yaml)
* Python Script with YAML Configuration (my future...)

I am only going to document the python script. The help in bash should
be intuitive enough to follow.

The CLI for backup.py is more slimmed down, in favour of configuration
more through YAML.

```bash
usage: backup.py [-h] --config YAML_FILE_PATH --project PROJECT_NAME [--backup]
                 [--restore RESTORE_FROM RESTORE_TO]

Back Up utility for incremental Tar Backups - Space Saving backups!

options:
  -h, --help            show this help message and exit
  --config, -c YAML_FILE_PATH
  --project, -p PROJECT_NAME
  --backup, -b
  --restore, -r RESTORE_FROM RESTORE_TO
```

```yaml
defaults:
  destination: /home/jonny/backups
  excludes: []
  compress: true
  retention:
    consolidate_after: 7 # Number of days
    keep_archives: 3

projects:
  docs:
    backup_filename: docs
    destination: /home/jonny/backups
    source: /home/jonny/Documents

  bingo:
    backup_filename: bingo_backup
    includes:
      - /home/jonny/bingo
      - /home/jonny/bingo1
    excludes:
      - .gitignore
```

The idea here is you setup a yaml configuration, setup cron and do scheduled backups.

To get started, it is fairly straight forward using UV.

```bash
uv sync
```

After this you are ready to go.

Due to the use of the YAML configuration, I was not fully happy with relative paths,
but i may introduce them. At present it is absolute paths only.

The options available in the examples are the only options available for
defaults and projects. Obviously you can rename your projects...

```yaml
projects:
  ollama:
    backup_filename: ...
```

An example of a cronjob...

```bash
crontab -e
```

```bash
30 20 * * * mount /mnt/backups/ && uv run --directory ~/git/backups-tar.gzip/ backup.py -c config.yaml -p nextcloud -b
```
