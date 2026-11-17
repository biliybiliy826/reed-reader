#!/bin/sh
set -eu
# Resolve the system /usr/bin symlink as well as paths containing spaces.
REED_EXECUTABLE=$(readlink -f -- "$0")
REED_DIRECTORY=$(dirname -- "$REED_EXECUTABLE")
unset PYTHONHOME PYTHONPATH
exec "$REED_DIRECTORY/runtime/bin/python3" -I -B -m reed_reader.app "$@"
