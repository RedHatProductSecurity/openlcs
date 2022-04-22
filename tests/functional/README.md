# Tests cases for API

Test cases are using tox and pytest for running the tests.


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

More info: https://docs.djangoproject.com/en/dev/topics/serialization/#natural-keys

Use this command to dump the DB:
```
python openlcs/manage.py dumpdata \
    packages auth.user auth.group adhoc comments history notifications \
    orgchart packages products reviews tasks utils authentications \
    --natural-foreign  -o database_data.json
```
Note: Do not forget to fill other tables (models) that you need
(e.g. newly created).
