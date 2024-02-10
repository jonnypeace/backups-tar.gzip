# Incremental Backups using tar and gzip compression

_update: 10-02-2024_

# The Concept
* The backup script holds onto 2 weeks worth of DAILY incremental backups
* This backup solution uses tar with or without gz compression.
* Once you've ensured that you are backing up all relevant files/directories, run on a crontab at a time each day which suits you. I recommend piping into logging command to capture any errors.
* If you have made an error during testing, it is _best to remove all the tar files (including the file.inc) and start over_.
* I've included a -h flag for help, which provides an example of backup and recovery. In the examples provided, i've named this script backup.sh.

Why this and not use tar directly?
Well...

* You could use tar directly, but the idea here is to manage a little more automation for tar.. Including:
  - 2 weeks worth of DAILY backups always organized
  - backups are incremental and automated therefore taking up less disk space.
  - Easier to remember syntax for recovery. What use is a backup, if you cant recover.
  - Compression and verbose enabled by default

## The backup & recovery script -h (help with examples)

```bash

    backup.sh script for backup and recovery.

    Select -b for backup followed by backup directory
    Select -r for recovery followed by location of backup directory
    Select -d for destination followed by directory to restore or backup to
    Select -f for name of backup file
    Select -n for no compression
    Select -e for excludes file.
    Select -h for this help

    backup.sh script for backup and recovery.

    Select -b for backup followed by backup directory
    Select -r for recovery followed by location of backup directory
    Select -d for destination followed by directory to restore or backup to
    Select -f for name of backup file
    Select -n for no compression
    Select -e for excludes file
    Select -i for includes file
    Select -h for this help

    DO NOT use -b WITH -i flag. If you want to add another directory or file, then add it to the includes file (-i) as there 
    should be no need to use both.

  * Example for backup:

      ./backup.sh -d /mnt/NFS/backup/ -f filename -b $HOME/files/

  * Example for restore:

      ./backup.sh -d $HOME/files/ -r /mnt/NFS/backup/

  * Example of backup utilizing the excludes file:

      ./backup.sh -d /mnt/NFS/backup/ -f filename -e excludes.file -b $HOME/files/
  
  * Example for no compression. Just add the -n flag, no further args required: 

      ./backup.sh -d /mnt/NFS/backup/ -n -f filename -e excludes.file -b $HOME/files/
  
  * Example for includes file
    (IMPORTANT: the -i flag cannot be used with -b ):

      ./backup.sh -d /mnt/NFS/backup/ -n -f filename -e excludes.file -i includes.file

```

## Potential improvements

* Considering the use of --one-file-system as a default or option.
* Considering making the backup timeline more flexible than 2 weeks of daily backups