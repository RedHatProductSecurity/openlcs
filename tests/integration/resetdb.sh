#!/bin/bash
# This is for the integration test. This test needs cleaning db due to test
# all the workflow. Because if the database won't be reset, the scanning will
# be deduplicated.
psql openlcs -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE datname='openlcs' AND pid<>pg_backend_pid();"
dropdb openlcs
createdb openlcs
