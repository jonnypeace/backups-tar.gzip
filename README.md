# Incremental Backups using tar .tgz

This should work independant of where the scripts are stored, from the backup directory.

# tarzip.sh - for incremental backup

I've added verbose to the backups, but if being run in a cron job, it's not really necessary.

Edit the script and update the directories as necessary (first few lines / variables)

~~~
# incremental backup directory
dirbk=/EDIT/ME/I/AM/YOUR/BACKUP/DIRECTORY

# directory to be backed up
dirfrom=/EDIT/ME/I/WANT/BACKED/UP

# incremental file which keeps track of changing
incfile=file.inc

# name of the file for back up, no extensions required here, just one word avoid spaces.
backfile=home
~~~

Edit the file variable name to suit your needs. "incfile=file.inc"

For cron, these are hard coded, no options in the command line, just full automation.

The scripts are set up for daily backups, storing 2 weeks worth of data.

Theres a corresponding script for restoring incremental backups, same idea, change the directories.

# rec-tarzip.sh for restoring

Edit these lines.
~~~
# incremental backup directory, where your backups are stored.
dirbk=/server-or-drive/that/stores/backups

# Directory to recover incremental backups to
# Example /home if you are recovering a users
# home directory, i.e. /home/user
recdir=/home
~~~
