# Incremental Backups using tar .tgz

These should work independant of where the scripts are stored.

# tarzip.sh

I've added verbose to the backups, but if being run in a cron job, it's not really necessary.

Edit the script and update the directories as necessary (first few lines / variables)

~~~
# incremental backup directory
dirbk=/EDIT/ME/I/AM/YOUR/BACKUP/DIRECTORY

# directory to be backed up
dirpass=/EDIT/ME/I/WANT/BACKED/UP

# incremental file which keeps track of changing
incfile=file.inc
~~~

Edit the file variable name to suit your needs. "incfile=file.inc"

For cron, these are hard coded, no options in the command line, just full automation.

The scripts are set up for daily backups, storing 2 weeks worth of data.

Theres a corresponding script for restoring incremental backups, same idea, change the directories.
