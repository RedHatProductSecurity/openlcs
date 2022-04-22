#!/bin/bash

set -eu

. "$(dirname "$0")/entrypoint-common.sh"

exec gunicorn "openlcs.wsgi"
