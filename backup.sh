#!/bin/bash

# Author: Jonny Peace
# This function will provide the tar.gz backup archive utilizing the incremental file for monitoring.
function backup {

  mkdir -p "$dirto"

  # incremental file which keeps track of changes (no need to change this)
  incfile=file.inc

  # date for directory and .tgz file naming
  day=$(date +'%F')

  #Check number of directories with week-ending, and count them
  dirnum=$(find "$dirto" -name "*week-ending*" -type d | wc -l)

  # My aim is to keep two weeks of backups at all times.
  # If you want to adjust this, adjust the number 3 accordingly.
  # Example: 3 will keep 2 full weeks of dailing backups.
  if [[ "$dirnum" -ge 3 ]]; then
    dir1=$(find "$dirto" -name "*week-ending*" | sort | awk 'NR==1{print}')
    rm -r "$dir1";
  fi

  # Counting the number .tgz files
  filenum=$(find "$dirto" -name "*.tgz" -type f | wc -l)

  # Once 7 .tgz are created, move them to a new week-ending directory
  # If run daily on cron job, this will be a weeks worth of incremental backups
  if [[ "$filenum" -ge 7 ]]; then
    mkdir -p "$dirto"/week-ending-"$day"
    mv "$dirto"/*.tgz "$dirto"/week-ending-"$day"
    mv "$dirto"/"$incfile" "$dirto"/week-ending-"$day"
  fi

  # Create .tgz file. Ideally this will work in a cron job, and you'll get daily backups
  # to exclude a directory after the tar command, example --exclude='/home/user/folder'
  if [[ -z "$no_comp" ]]; then
    if [[ -z "$exc_file" ]]; then
      tar -vcz -g "$dirto"/"$incfile" -f "$dirto"/"$backfile"-"$day".tgz "$dirfrom"
    else
      tar -vcz -g "$dirto"/"$incfile" -X "$exc_file" -f "$dirto"/"$backfile"-"$day".tgz "$dirfrom"
    fi
  else
    if [[ -z "$exc_file" ]]; then
      tar -vc -g "$dirto"/"$incfile" -f "$dirto"/"$backfile"-"$day".tar "$dirfrom"
    else
      tar -vc -g "$dirto"/"$incfile" -X "$exc_file" -f "$dirto"/"$backfile"-"$day".tar "$dirfrom"
    fi
  fi
}

# This function will recover the data, and requires all tar files from the backup directory and the incremental file.
# the -g /dev/null happens for tar to be happy.
function recovery {

  mkdir -p "$dirto"

  for file in "$dirbk"/*.tgz ; do
    tar -vx -g /dev/null -f "$file" -C "$dirto"
  done

}

# This loop relies on the commandline flags so it knows which function to choose.
# The reason for the if statements is to account for user input, and whether they include 
# a forward slash at the end.
while getopts b:r:d:e:f:nh opt
do
  case "$opt" in
    
    b) 
      dirfrom="$OPTARG"
      if [[ "${dirfrom:0-1}" == '/' ]] ; then dirfrom="${dirfrom::-1}"; fi
      backup ;;
    r)
      dirbk="$OPTARG"
      if [[ "${dirbk:0-1}" == '/' ]] ; then dirbk="${dirbk::-1}"; fi
      recovery ;;
    d)
      dirto="$OPTARG"
      if [[ "${dirto:0-1}" == '/' ]] ; then dirto="${dirto::-1}"; fi;;
    e)
      exc_file="$OPTARG" ;;
    n)
      no_comp='true' ;;
    f)
      backfile="$OPTARG" ;;
    h)
    cat << EOF

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

EOF
    exit ;;
    *)
      echo 'Incorrect option selected, run ./backup.sh -h for help' 
      exit
  esac
done