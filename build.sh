#!/bin/bash

set -e

SCRIPT_DIR=$(dirname ${BASH_SOURCE})
cd "$SCRIPT_DIR"

exec "tools/packman/python.sh" tools/repoman/build.py $@

exec "tools/gather_licenses.sh
