#!/bin/bash

# Author: Jonny Peace

#### If includes_file and dirfrom, then exit with error.
if [[ $* =~ ' -b ' && $* =~ ' -i ' ]]; then
  printf '\033[91m%s\033[0m\n\n' "When using -i, do not use -b or errors occur. You may as well add all directories to the include file and start again"
  exit 1
fi

function sense_check {
  echo "Destination Directory set: ${dirto:?'-d (destination) is not set. Exiting.'}"
  backfile="${backfile:-backupfile}"
}

function check_includes {
  [[ ! -f "$includes_file" ]] &&
    echo "Error: Includes File (-i) is not an actual file ${includes_file:-Includes_File_Not_Set}" &&
    exit 1   
}

function check_excludes {
  [[ ! -f "$excludes_file" ]] &&
    echo "Error: Excludes File (-e) is not an actual file ${excludes_file:-Excludes_File_Not_Set}" &&
    exit 1   
}

function check_dirbk {
  [[ ! -d "$dirbk" ]] &&
    echo "Error: Destination directory '$dirbk' does not exist." &&
    exit 1
}

function check_backup_dir {
  [[ ! -d "$dirfrom" ]] &&
    echo "Error: Backup Directory (-b) does not exist; ${dirfrom:-Backup_Dir_Not_Set}, exitting." &&
    exit 1
}

# This function will provide the tar.gz backup archive utilizing the incremental file for monitoring.
function backup {

  sense_check
  mkdir -p "$dirto"
  # incremental file which keeps track of changes (no need to change this)
  incfile=file.inc

  # date for directory and .tgz file naming
  # format example 2023-05-28_23.10.05
  # yyyy-mm-dd_h.m.s 
  day=$(printf '%(%Y-%m-%d_%H.%M.%S)T\n')

  # Enable nullglob to ensure arrays are empty if no matching files are found
  shopt -s nullglob
  #Check number of directories with week-ending, and count them
  dirnum=0
  for dir in "$dirto"/*week-ending*/; do
      [[ -d "$dir" ]] && ((dirnum++))
  done

  # My aim is to keep two weeks of backups at all times.
  # If you want to adjust this, adjust the number 3 accordingly.
  # Example: 3 will keep 2 full weeks of dailing backups.
  backup_dirs=("$dirto"/*week-ending*/)
  if [[ ${#backup_dirs[@]} -ge 3 ]]; then
      # The naming convention includes sortable date strings,
      # simply sorting the names alphabetically should suffice.
      # More so if this directory is only used by this script.
      oldest_dir="${backup_dirs[0]}"
      echo "Removing oldest directory: $oldest_dir"
      rm -r "$oldest_dir"
  fi

  tar_files=("$dirto"/*.tar "$dirto"/*.tar.gz "$dirto"/*.tgz)
  filenum=${#tar_files[@]}
  shopt -u nullglob

  # Once 7 .tgz are created, move them to a new week-ending directory
  # If run daily on cron job, this will be a weeks worth of incremental backups
  if [[ "$filenum" -ge 7 ]]; then
    arch_dir="${dirto}/week-ending-${day%_*}"
    mkdir -p "$arch_dir"
    mv "$dirto"/*.tar* "$arch_dir"
    mv "$dirto"/"$incfile" "$arch_dir"
  fi

  # Create .tgz file. Ideally this will work in a cron job, and you'll get daily backups
  # to exclude a directory after the tar command, example --exclude='/home/user/folder'
  declare -a args
  if [[ "${no_comp}" ]]; then
    args=("-vc" "-g" "${dirto}/${incfile}" "-f" "${dirto}/${backfile}-${day}.tar")
  else
    args=("-vcz" "-g" "${dirto}/${incfile}" "-f" "${dirto}/${backfile}-${day}.tar.gz")
  fi

  if [[ "${includes_file}" ]]; then
    [[ ! -f "${includes_file}" ]] && 
      echo "Includes File Not a File: ${includes_file}" && exit 1
    args+=("-T" "${includes_file}")
  else
    args+=("${dirfrom}")
  fi

  if [[ "${excludes_file}" ]]; then
    [[ ! -f "${excludes_file}" ]] && 
    echo "Excludes File Not a File: ${excludes_file}" && exit 1
    args=("-X" "${excludes_file}" "${args[@]}")

  fi

  tar "${args[@]}"
}

# This function will recover the data, and requires all tar files from the backup directory and the incremental file.
# the -g /dev/null keeps tar happy.
# 
function recovery {
  sense_check
  (mkdir -p "$dirto"
  shopt -s nullglob
  shopt -s globstar
  for file in "$dirbk"/**/*.tar*; do
    tar -vx -g /dev/null -f "$file" -C "$dirto"
  done)
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
      check_backup_dir;;
    r)
      dirbk="$OPTARG"
      if [[ "${dirbk:0-1}" == '/' ]] ; then dirbk="${dirbk::-1}"; fi
      check_dirbk ;;
    d)
      dirto="$OPTARG"
      if [[ "${dirto:0-1}" == '/' ]] ; then dirto="${dirto::-1}"; fi;;
    e)
      excludes_file="$OPTARG"
      check_excludes ;;
    n)
      no_comp='true' ;;
    i)
      includes_file="$OPTARG"
      check_includes;;
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

  * Example for backup:

      ./backup.sh -d /mnt/NFS/backup/ -f filename -b $HOME/files/

  * Example for restore:

      ./backup.sh -d $HOME/files/ -r /mnt/NFS/backup/

  * Example of backup utilizing the excludes file:

      ./backup.sh -d /mnt/NFS/backup/ -f filename -e excludes.file -b $HOME/files/
  
  * Example for no compression. Just add the -n flag, no further args required: 

      ./backup.sh -d /mnt/NFS/backup/ -n -f filename -e excludes.file -b $HOME/files/
  
  * Example for includes file
    (IMPORTANT: the -i flag cannot be used with -b ):

      ./backup.sh -d /mnt/NFS/backup/ -n -f filename -e excludes.file -i includes.file

EOF
    exit ;;
    *)
      echo 'Incorrect option selected, run ./backup.sh -h for help' 
      exit
  esac
done

[[ -z "$dirfrom" && -z "$includes_file" ]] &&
  echo "Required an option of -b backup directory or -i includes file, exitting..." && exit 1

[[ -n "$dirfrom" || -n "$includes_file" ]] && backup

[[ -n "$dirbk" && -n "$dirto" ]] && recovery