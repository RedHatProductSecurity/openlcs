#!/bin/sh

set -eu

. "$(dirname "$0")/entrypoint-common.sh"

exec python -m celery -A pelcd worker "$@"
