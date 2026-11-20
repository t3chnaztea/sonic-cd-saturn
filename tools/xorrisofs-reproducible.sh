#!/bin/sh
# xorrisofs with fixed dates, for Yaul's make-iso (MAKE_ISO_XORRISOFS).
#
# Every ISO 9660 date (volume creation/modification and every file and
# directory record) comes from one value, so two builds of the same tree give
# the same image. File mtimes in cd/ are never used. The value is
# SOURCE_DATE_EPOCH if set, else IP_RELEASE_DATE from the Makefile (00:00 UTC),
# else the HEAD commit time. IP_RELEASE_DATE comes before the commit time
# because it is part of the tree: a release rebuilt from its tag gets the
# same image even when the build ran before the commit.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
real=${SCD_XORRISOFS:-$(command -v xorrisofs)}
case "$real" in
    */xorrisofs-reproducible.sh|'') echo "xorrisofs-reproducible.sh: set SCD_XORRISOFS to the real xorrisofs" >&2; exit 1;;
esac
case "${1:-}" in
    --help|-version|--version) exec "$real" "$@";;
esac
epoch=${SOURCE_DATE_EPOCH:-}
if [ -z "$epoch" ]; then
    day=$(sed -n 's/^IP_RELEASE_DATE *:*= *\([0-9]\{8\}\) *$/\1/p' "$root/Makefile" | head -n 1)
    if [ -n "$day" ]; then
        epoch=$(python3 -c "import calendar,time,sys;print(calendar.timegm(time.strptime(sys.argv[1],'%Y%m%d')))" "$day")
    else
        epoch=$(git -C "$root" log -1 --format=%ct)
    fi
fi
case "$epoch" in
    ''|*[!0-9]*) echo "xorrisofs-reproducible.sh: invalid date epoch '$epoch'" >&2; exit 1;;
esac
stamp=$(python3 -c "import time,sys;print(time.strftime('%Y%m%d%H%M%S00',time.gmtime(int(sys.argv[1]))))" "$epoch")
SOURCE_DATE_EPOCH=$epoch TZ=UTC exec python3 "$root/tools/package_reuse.py" iso "$real" --modification-date="$stamp" --set_all_file_dates "=$epoch" "$@"
