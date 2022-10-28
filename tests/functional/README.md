# Tests cases for API

Test cases are using tox and pytest for running the tests.

## Configure environment variables for test cases

Depending on the local configuration, you may need to update some of below variables for the tests to succeed:

- OLCS_SCANCODE_CLI: full path to the `scancode` executable
- OLCS_EXTRACTCODE_CLI: full path to the `extractcode` executable
- OLCS_TEST_DB_NAME: test database name
- OLCS_TEST_DB_HOST: test database host
- OLCS_TEST_DB_PORT: test database port
- OLCS_TEST_DB_USER: test database username
- OLCS_TEST_DB_HOST: test database password

>Note: each of the variable above has a default value, only update those that are inconsistent with the default.

## Run the tests
There are a few methods how you can run test cases. Always run the commands from
openlcs root directory.

1. Run all tests using `tox`
2. Run just test all API cases: `tox -e api -- -v --reuse-db`
3. Run test for one method: `tox -e api -- --reuse-db -v tests/functional/api/test_module.py::test_method`


### Tips

When testing a new version that added new migrations, run once without `--reuse-db`.

#### Producing a report

Add `--html report.html` argument to `tox` invocation after `--` separator.


#### Debugging tests

To debug a failed test, pass a `--pdb` option to tox after `--` separator. It
will pause the test after the failure, when you can access the server and
database.
You can run the printed curl commands without modifications.
You can access the server via the URL printed in curl commands.
You can access the database using: `psql test_openlcs`.
To exit the paused test, use Ctrl+C.


#### Creating data dump for tests

When you are creating a dump for the tests it is necessary to create it with
`--natural-foreign` parameter otherwise the tests will fail due to inconsistent
IDs of `django_content_type` and others.

Warning:

You should `never` include automatically generated objects in a fixture or other serialized data.
By chance, the primary keys in the fixture may match those in the database and loading the fixture will have no effect.
In the more likely case that they don’t match, the fixture loading will fail with an IntegrityError.

More info: https://docs.djangoproject.com/en/3.2/topics/serialization/#topics-serialization-natural-keys

Use this command to dump the DB:
```
python openlcs/manage.py dumpdata \
    auth.user packages.file packages.source packages.path tasks \
    --natural-foreign -o database_data.json --indent 4
```
Note: Do not forget to fill other tables (models) that you need
(e.g. newly created).

More info: https://docs.djangoproject.com/en/3.2/ref/django-admin/#dumpdata 
