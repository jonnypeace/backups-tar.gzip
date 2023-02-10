# Incremental Backups using tar and gzip compression

_update: 10-02-2023_

# The Concept
* There is one script now after this _recent update_, which does both backup & restore.
* The backup script holds onto 2 weeks worth of incremental backups
* This backup solution uses tar with gz compression.
* Once you've ensured that you are backing up all relevant files/directories, run on a crontab at a time which suits you.
* If you have made an error during testing, it is _best to remove all the files (including the file.inc) and start over_.
* I've included a -h flag for help, which provides an example of backup and recovery. In the examples provided, i've named this script backup.sh.

## The backup & recovery script

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