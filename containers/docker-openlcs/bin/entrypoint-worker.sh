#!/bin/bash

set -eu

. "$(dirname "$0")/entrypoint-common.sh"

exec python -m celery -A openlcsd worker "$@"
