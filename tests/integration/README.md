# Integration testing

Test cases are using tox and pytest for running the tests.

## Debug the integration tests

Since integration tests are different with unit test and api test, it requires
to deploy the latest patch to the openlcs-ci environment. Besides that, when
manually debug the test cases, **make sure there are no pipeline running**.
You should always run the commands from OpenLCS root directory.

1. `oc login --token=xxx --server=$OCP_CONSOLE`
2. `oc project openlcs--ci`
3. `oc rsh $gunicorn`
5. `kinit "Your name"@IPA.REDHAT.COM`
6. `export OPENLCS_TEST_URL="$OPENLCS_TEST_URL"`
7. `tox -e  integration --  -v tests/integration/$testfile.py`
