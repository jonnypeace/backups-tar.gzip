#!/bin/bash

# Author: Jonny Peace

#### If includes_file and dirfrom, then exit with error.
if [[ $* =~ ' -b ' && $* =~ ' -i ' ]]; then
  printf '\033[91m%s\033[0m\n\n' "When using -i, do not use -b or errors occur. You may as well add all directories to the include file and start again"
  exit 1
fi

# This function will provide the tar.gz backup archive utilizing the incremental file for monitoring.
function backup {

  mkdir -p "$dirto"

  # incremental file which keeps track of changes (no need to change this)
  incfile=file.inc

  # date for directory and .tgz file naming
  # format example 2023-05-28_23.10.05
  # yyyy-mm-dd_h.m.s 
  day=$(printf '%(%Y-%m-%d_%H.%M.%S)T\n')

  #Check number of directories with week-ending, and count them
  dirnum=$(find "$dirto" -name "*week-ending*" -type d | wc -l)

  # My aim is to keep two weeks of backups at all times.
  # If you want to adjust this, adjust the number 3 accordingly.
  # Example: 3 will keep 2 full weeks of dailing backups.
  if [[ "$dirnum" -ge 3 ]]; then
    dir1=$(find "$dirto" -name "*week-ending*" -type d | sort | head -n1)
    rm -r "$dir1";
  fi

  # Counting the number .tgz files
  filenum=$(find "$dirto" -maxdepth 1 -name "*.tar*" -type f | wc -l)

  # Once 7 .tgz are created, move them to a new week-ending directory
  # If run daily on cron job, this will be a weeks worth of incremental backups
  if [[ "$filenum" -ge 7 ]]; then
    arch_dir="$dirto"/week-ending-"${day%_*}"
    mkdir -p "$arch_dir"
    mv "$dirto"/*.tar* "$arch_dir"
    mv "$dirto"/"$incfile" "$arch_dir"
  fi

  # Create .tgz file. Ideally this will work in a cron job, and you'll get daily backups
  # to exclude a directory after the tar command, example --exclude='/home/user/folder'

  if [[ "${no_comp}" ]]; then
    args="-vc -g ${dirto}/${incfile} -f ${dirto}/${backfile}-${day}.tar"
  else
    args="-vcz -g ${dirto}/${incfile} -f ${dirto}/${backfile}-${day}.tar.gz"
  fi

  if [[ "${includes_file}" ]]; then
    args="${args} -T ${includes_file}"
  else
    args="${args} ${dirfrom}"
  fi

  if [[ "${exc_file}" ]]; then
    args="-X ${exc_file} ${args}"
  fi

  tar ${args}
}

# This function will recover the data, and requires all tar files from the backup directory and the incremental file.
# the -g /dev/null happens for tar to be happy.
function recovery {

  mkdir -p "$dirto"

  for file in "$dirbk"/*.tar* ; do
    tar -vx -g /dev/null -f "$file" -C "$dirto"
  done

}

# This loop relies on the commandline flags so it knows which function to choose.
# The reason for the if statements is to account for user input, and whether they include 
# a forward slash at the end.
while getopts b:r:d:e:f:ni:h opt
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
    i)
      includes_file="$OPTARG"
      backup;;
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
    Select -e for excludes file
    Select -i for includes file
    Select -h for this help

    DO NOT use -b WITH -i flag. If you want to add another directory or file, then add it to the includes file (-i) as there 
    should be no need to use both.

  * Example for backup (IMPORTANT: the -b flag comes at end of command):

      ./backup.sh -d /mnt/NFS/backup/ -f filename -b $HOME/files/

  * Example for restore (IMPORTANT: the -r flag comes at end of command):

      ./backup.sh -d $HOME/files/ -r /mnt/NFS/backup/

  * Example of backup utilizing the excludes file (IMPORTANT: the -b flag comes at end of command):

      ./backup.sh -d /mnt/NFS/backup/ -f filename -e excludes.file -b $HOME/files/
  
  * Example for no compression. Just add the -n flag, no further args required 
    (IMPORTANT: the -b flag comes at end of command):

      ./backup.sh -d /mnt/NFS/backup/ -n -f filename -e excludes.file -b $HOME/files/
  
  * Example for includes file
    (IMPORTANT: the -i flag comes at end of command with NO -b ):

      ./backup.sh -d /mnt/NFS/backup/ -n -f filename -e excludes.file -i includes.file

EOF
    exit ;;
    *)
      echo 'Incorrect option selected, run ./backup.sh -h for help' 
      exit
  esac
done
