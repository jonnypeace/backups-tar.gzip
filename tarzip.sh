#!/bin/bash

# incremental backup directory
dirbk=/EDIT/ME/I/AM/YOUR/BACKUP/DIRECTORY

# directory to be backed up
dirfrom=/home/user

# incremental file which keeps track of changing
incfile=file.inc

# name of the file for back up, no extensions required here, just one word, avoid spaces.
backfile=home

# date for directory and .tgz file naming
day=$(date +'%F')

#Check number of directories with week-ending, and count them
dirnum=$(find "$dirbk"/*week-ending* -type d 2> /dev/null | wc -l)

# My aim is to keep two weeks of backups at all times. 
# If you want to adjust this, adjust the number 3 accordingly.
# Example: 3 will keep 2 full weeks of dailing backups.
if [[ "$dirnum" -ge 3 ]]; then
	dir1=$(find "$dirbk"/*week-ending* -type d 2> /dev/null | sort | awk 'NR==1{print}')
	rm -r "$dir1";
fi

# Counting the number .tgz files
filenum=$(find "$dirbk"/*.tgz -type f 2> /dev/null | wc -l)

# Once 7 .tgz are created, move them to a new week-ending directory
# If run daily on cron job, this will be a weeks worth of incremental backups
if [[ "$filenum" -ge 7 ]]; then
	mkdir -p "$dirbk"/week-ending-"$day"
	mv "$dirbk"/*.tgz "$dirbk"/week-ending-"$day"
	mv "$dirbk"/"$incfile" "$dirbk"/week-ending-"$day"
fi

# Create .tgz file. Ideally this will work in a cron job, and you'll get daily backups
# to exclude a directory after the tar command, example --exclude='/home/user/folder'
tar -vcz -g "$dirbk"/"$incfile" -f "$dirbk"/"$backfile"-"$day".tgz "$dirfrom"
