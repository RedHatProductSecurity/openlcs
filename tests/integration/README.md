# Integration testing

Test cases are using tox and pytest for running the tests.

## Debug the IT tests

Since IT tests are different with UI test, it requires to reset database after every running time,
besides that, when manually debug it test cases, **make sure there are no pipeline running**.
You should always run the commands from OpenLCS root directory.
Here just list process about how to debug large package cases and small packages are the same.

1. `oc login --server=$OCP_CONSOLE`
2. `oc project openlcs--ci`
//Reset database
3. `oc rsh dc/database bash -c "bash /tmp/reset-database.sh $openlcs_db_file > /dev/null"`
//sync database again
4. `oc rsh dc/web bash -c "openlcs/manage.py migrate --noinput"`
5. `kinit "Your name"@REDHAT.COM`
6. `export OLCS_TEST_URL="https://$(oc -n $OLCS_PROJECT get route web -o jsonpath='{.spec.host}')"`
7. `tox -e integration-large -- /path/to/your_debug_file::your_test_case`
