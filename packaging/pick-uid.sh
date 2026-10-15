#!/bin/sh
# Print a free system uid that is not in /etc/passwd and not used by a live process.
# Usage: . packaging/pick-uid.sh; pick_atlas_uid
pick_atlas_uid() {
  used=$(awk -F: '{print $3}' /etc/passwd 2>/dev/null || true)
  live=$(awk '/^Uid:/{print $2}' /proc/[0-9]*/status 2>/dev/null | sort -u || true)
  for candidate in 980 981 982 983 984 985 986 987 988 989 990 991 992 993 994 995 996 997 998 \
    900 901 902 903 904 905 906 907 908 909 910 911 912 913 914 915 916 917 918 919; do
    echo "$used" | grep -qx "$candidate" && continue
    echo "$live" | grep -qx "$candidate" && continue
    echo "$candidate"
    return 0
  done
  echo "No free system uid was found for atlas." >&2
  return 1
}
