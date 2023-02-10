#!/bin/bash

# incremental backup directory where your backup tar files are kept
dirbk=/backup/directory

# Directory to recover incremental backups to
recdir="$HOME"/recovered

mkdir -p "$recdir"

cd "$recdir" || exit

for f in "$dirbk"/*.tgz ; do
	tar -x -g /dev/null -f "$f"
done
