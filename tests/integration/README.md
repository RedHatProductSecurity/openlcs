# Integration testing

Test cases are using tox and pytest for running the tests.

## Debug the integration tests

Since integration tests are different with unit test and api test, it requires
to deploy the latest patch to the openlcs-ci environment. Besides that, when
manually debug the test cases, **make sure there are no pipeline running**.
You should always run the commands from OpenLCS root directory.

1. `oc login --token=xxx --server=$OCP_CONSOLE`
2. `oc project openlcs--ci`
3. `oc exec -it $pod_db /bin/bash "tests/integration/resetdb.sh"` 
4. `oc rsh $gunicorn`
5. `openlcs/manage.py migrate --noinput`
6. `kinit "Your name"@IPA.REDHAT.COM`
7. `export OPENLCS_TEST_URL="$OPENLCS_TEST_URL"`
8. `export CORGI_API_STAGE="$CORGI_API_STAGE"`
9. `export TEST_PACKAGE_NAME=$TEST_PACKAGE_NAME`
10. `tox -e  integration --  -v tests/integration/$testfile.py`
