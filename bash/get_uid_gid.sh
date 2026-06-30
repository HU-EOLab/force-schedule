#!/bin/bash
# returns the user and groupd id

# Function to convert user:group to uid:gid
convert_to_uid_gid() {
    local input="$1"
    
    # If no input provided, return current user:group
    if [ -z "$input" ]; then
        echo "$(id -u):$(id -g)"
        return
    fi
    
    # If already in numeric format, return as-is
    if [[ "$input" =~ ^[0-9]+:[0-9]+$ ]]; then
        echo "$input"
        return
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
}

# Main execution
USER_GROUP="${1:-}"
convert_to_uid_gid "$USER_GROUP"
