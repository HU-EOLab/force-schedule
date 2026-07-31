#!/bin/bash
# returns the user and group id
# Usage: get-uid-gid.sh "user:group"  or  get-uid-gid.sh (reads from config)

# Function to convert user:group to uid:gid
convert_to_uid_gid() {
    local input="$1"
    
    # If no input provided, return current user:group
    if [ -z "$input" ]; then
        echo "$(id -u):$(id -g)"
        return 0
    fi
    
    # If already in numeric format, return as-is
    if [[ "$input" =~ ^[0-9]+:[0-9]+$ ]]; then
        echo "$input"
        return 0
    fi
    
    # Parse user:group
    local user_part="${input%:*}"
    local group_part="${input#*:}"
    
    # Get UID
    local uid=$(id -u "$user_part" 2>/dev/null)
    if [ $? -ne 0 ]; then
        echo "Error: user '$user_part' not found" >&2
        return 1
    fi
    
    # Get GID
    local gid=$(getent group "$group_part" | cut -d: -f3)
    if [ -z "$gid" ]; then
        echo "Error: group '$group_part' not found" >&2
        return 1
    fi
    
    echo "$uid:$gid"
    return 0
}

# Main execution
if [ $# -ge 1 ]; then
    # Argument provided - convert it
    convert_to_uid_gid "$1"
else
    # No argument - read from config using read-config2.sh
    # Find the script directory
    BIN="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
    
    # Look for config file - check command line args first
    CONFIG=""
    shift_count=0
    for arg in "$@"; do
        case $arg in
            --config=*)
                CONFIG="${arg#*=}"
                shift_count=$((shift_count + 1))
                ;;
            --config)
                if [ $# -ge 2 ]; then
                    CONFIG="$2"
                    shift_count=$((shift_count + 2))
                fi
                ;;
        esac
    done
    
    # If no config found in args, use default
    if [ -z "$CONFIG" ]; then
        CONFIG="../config/config.txt"
    fi
    
    USER_GROUP=$("$BIN"/read-config2.sh "USER_GROUP" "$CONFIG" "$(id -u):$(id -g)")
    convert_to_uid_gid "$USER_GROUP"
fi