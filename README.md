# Incremental Backups using tar and gzip compression

_update: 10-02-2023_

# The Concept
* There is one script now after this _recent update_, which does both backup & restore.
* The backup script holds onto 2 weeks worth of DAILY incremental backups
* This backup solution uses tar with gz compression.
* Once you've ensured that you are backing up all relevant files/directories, run on a crontab at a time each day which suits you.
* If you have made an error during testing, it is _best to remove all the backup files (including the file.inc) and start over_.
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

  * Example for backup (IMPORTANT: the -b flag comes at end of command):

      ./backup.sh -d /mnt/NFS/backup/ -f filename -b $HOME/files/

  * Example for restore (IMPORTANT: the -r flag comes at end of command):

      ./backup.sh -d $HOME/files/ -r /mnt/NFS/backup/

  * Example of backup utilizing the excludes file (IMPORTANT: the -b flag comes at end of command):

      ./backup.sh -d /mnt/NFS/backup/ -f filename -e excludes.file -b $HOME/files/
  
  * Example for no compression. Just add the -n flag, no further args required:

      ./backup.sh -d /mnt/NFS/backup/ -n -f filename -e excludes.file -b $HOME/files/

```

## Potential improvements

* Considering the use of --one-file-system as a default or option.
* Considering making the backup timeline more flexible than 2 weeks
* Implement a more regular routine for backups, rather than limiting to daily.