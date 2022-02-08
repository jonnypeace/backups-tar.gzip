#!/bin/bash

# incremental backup directory
dirbk=/EDIT/ME/I/AM/YOUR/BACKUP/DIRECTORY

# directory to be backed up
dirpass=/EDIT/ME/I/WANT/BACKED/UP

# incremental file which keeps track of changing
incfile=file.inc

# date for directory and .tgz file naming
day=$(date +'%F')

#Check number of directories with week-ending, and count them
dirnum=$(find $dirbk/*week-ending* -type d | wc -l)

# My aim is to keep two weeks of backups at all times. 
# If you want to adjust this, adjust the number 3 accordingly.
# Example: 3 will keep 2 full weeks of dailing backups.
if [[ $dirnum -ge 3 ]]; then
	dir1=$(find $dirbk/*week-ending* -type d | sort | awk 'NR==1{print}')
	rm -r $dir1;
fi

# Counting the number .tgz files
filenum=$(find $dirbk/*.tgz -type f | wc -l)

# Once 7 .tgz are created, move them to a new week-ending directory
# If run daily on cron job, this will be a weeks worth of incremental backups
if [[ $filenum -ge 7 ]]; then
	mkdir -p $dirbk/week-ending-$day
	mv $dirbk/*.tgz $dirbk/week-ending-$day
	mv $dirbk/$incfile $dirbk/week-ending-$day
fi

# Create .tgz file. Ideally this will work in a cron job, and you'll get daily backups
tar -vvcz -g $dirbk/$incfile -f $dirbk/pass-$day.tgz $dirpass
