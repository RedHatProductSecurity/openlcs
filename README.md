# PELC2

The next generation of PELC

## Setting up development environment
This section assumes you're running sufficiently recent version of RHEL 8 
(OCP environment using this version).

### Setting up database
```shell
# Install packages
sudo dnf install postgresql postgresql-server
# Initialize schemas
sudo postgresql-setup --initdb
# Allow access for local users without password
sudo sed -ri '/^[^#]/s/ident|peer/trust/' /var/lib/pgsql/data/pg_hba.conf
# Start postgres
sudo systemctl enable --now postgresql
# Create role for pelc2
psql -U postgres <<< "CREATE ROLE pelc2 SUPERUSER LOGIN"
# Create role for yourself, so that you don't have to use -U postgres all the time
psql -U postgres <<< "CREATE ROLE $USER SUPERUSER LOGIN"
# Create pelc2 schemas
createdb pelc2
# Import a schemas dump
# curl https://gitlab.cee.redhat.com/pelc/pelc-db-dumper/-/jobs/2152496/artifacts/raw/pelc-db-it.sql.gz \
#    | gunzip -cd | psql pelc
```

Hint: you can put `export PGDATABASE=pelc2` into your `.bashrc`, 
and then you don't have to specify `pelc2` as the database when using `psql`.
And if configured postgresql, ignore the configure steps, only update
the database.

### Setting up Redis
```shell
# Install redis
sudo dnf install redis
# Start redis and enable it on startup
sudo systemctl enable --now redis
```

### Setting up PELC2
```shell
# Install rpm dependencies
sudo dnf install python38 python38-devel virtualenvwrapper gcc
# Setup virtualenv
echo "
# Set virtualenv
export WORKON_HOME=$HOME/.virtualenvs
source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
# Reload bash to pick up newly installed functions for virtualenv
exec bash
# Create a new virtualenv named pelc2
mkvirtualenv pelc2 --python /usr/bin/python3.8
# Set $VIRTUAL_ENV
VIRTUAL_ENV=~/.virtualenvs/$ENV_NAME

# Set CA for requests library in the virtualenv
echo "export REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt" \
    > $VIRTUAL_ENV/bin/postactivate
source $VIRTUAL_ENV/bin/postactivate

# Install Python dependencies
pip install -r requirements/devel.txt

# Create soft links under $(PYTHON_SITELIB)
cd $VIRTUAL_ENV/lib/python3.8/site-packages
ln -snf /pelc_project_path/pelcd

# Execute migrations
pelc/manage.py migrate --noinput
# Create admin account, use name `admin` and password `test`
pelc/manage.py createsuperuser

# Install atool
sudo cp containers/repos/pelc.repo /etc/yum.repos.d/
sudo dnf install atool

# Install typecode patch
cd $VIRTUAL_ENV/lib/python3.8/site-packages/typecode
patch < /pelc_project_path/containers/patches/magic2.patch
```

Virtualenv note: When opening a new shell, you need to activate the virtualenv
using `workon pelc2`.

### Running PELC2 web interface
PELC2 web interface can be started for local development (built-in server with
auto reloading) using the following under pelc_project_path:
```shell
gunicorn pelc.wsgi
```

It can be accessed on http://localhost:8000/. You can log in by going to
http://127.0.0.1:8000/admin/login/ and using the account you set up in 
the previous section (user `admin`, password `test`).

### Running PELC2 worker
PELC2 worker can be started using the following (from the top directory of 
the repo):
```shell
celery -A pelcd worker --loglevel=INFO
# If you want to debug using celery log, use:
celery -A pelcd worker --loglevel=DEBUG
```

Hint: You can remove all currently queued tasks using `redis-cli FLUSHALL`.


### How to add unit test cases for PELC2
```text
For Django app, add test cases in tests.py.
For lib in Django, add test cases in tests.py.
For workflow in pelcd/pelcflow/tasks.py, write test files in tests,
and add test file in suite defined in __init__.py
```
