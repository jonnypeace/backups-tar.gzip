#!/bin/bash

# incremental backup directory
dirbk=/backup/directory

# Directory to recover incremental backups to
recdir="$HOME"/recovered

mkdir -p "$recdir"

cd "$recdir"

for f in $(find "$dirbk" -type f -iname "*.tgz" | sort -n) ; do
	tar -x -g /dev/null -f "$f"
done
