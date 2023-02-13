#!/bin/bash

set -eu

. "$(dirname "$0")/entrypoint-common.sh"

cd /opt/app-root/src/openlcs
exec python -m celery -A openlcs beat "$@"
