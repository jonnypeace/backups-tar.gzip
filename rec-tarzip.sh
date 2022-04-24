#!/bin/bash

# incremental backup directory
dirbk=/server-or-drive/that/stores/backups

# Directory to recover incremental backups to
# Example /home if you are recovering a users
# home directory, i.e. /home/user
recdir=/home

for f in $(ls -tr "$dirbk"/*.tgz) ; do
	cd "$recdir" && tar -x -g /dev/null -f "$f"
done
