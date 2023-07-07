# OpenLCS

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
# Create role for openlcs
psql -U postgres <<< "CREATE ROLE openlcs SUPERUSER LOGIN"
# Create role for yourself, so that you don't have to use -U postgres all the time
psql -U postgres <<< "CREATE ROLE $USER SUPERUSER LOGIN"
# Create openlcs schemas
createdb openlcs
```

Hint: you can put `export PGDATABASE=openlcs` into your `.bashrc`,
and then you don't have to specify `openlcs` as the database when using `psql`.
And if configured postgresql, ignore the configure steps, only update
the database.

### Setting up Redis
```shell
# Install redis
sudo dnf install redis
# Start redis and enable it on startup
sudo systemctl enable --now redis
```

### Setting up OpenLCS
```shell
# Install rpm dependencies
# postgresql-devel used by install psycopg2
# If cannot install virtualenvwrapper, use pip to install it
sudo dnf install python38 python38-devel postgresql-devel virtualenvwrapper gcc patch docker-ce-cli skopeo

# Setup virtualenv
echo "
# Set virtualenv
export WORKON_HOME=$HOME/.virtualenvs
source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
# Reload bash to pick up newly installed functions for virtualenv
exec bash
# Create a new virtualenv named openlcs
mkvirtualenv openlcs --python /usr/bin/python3.8
# Set $VIRTUAL_ENV
VIRTUAL_ENV=~/.virtualenvs/openlcs
# Set CA for requests library in the virtualenv
echo "export REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt" \
    > $VIRTUAL_ENV/bin/postactivate
source $VIRTUAL_ENV/bin/postactivate
workon openlcs

# Install project dependencies
pip install -r requirements/devel.txt
# If cannot install psycopg2, install psycopg2-binary instead
# using "pip install psycopg2-binary==2.9.2"

# Create soft links under $(PYTHON_SITELIB)
cd $VIRTUAL_ENV/lib/python3.8/site-packages
ln -snf /openlcs_project_path/openlcsd

# Execute migrations
openlcs/manage.py migrate --noinput
# Create admin account, use name `admin` and password `test`
openlcs/manage.py createsuperuser

# Install atool(0.39.0)
Package available in https://src.fedoraproject.org/rpms/atool

# Install typecode patch
cd $VIRTUAL_ENV/lib/python3.8/site-packages/typecode
patch < /openlcs_project_path/containers/patches/magic2.patch
```

Virtualenv note: When opening a new shell, you need to activate the virtualenv
using `workon openlcs`.

### Running OpenLCS web interface
OpenLCS web interface can be started for local development (built-in server with
auto reloading) using the following under openlcs_project_path:
```shell
gunicorn openlcs.wsgi
# or
openlcs/manage.py runserver 0:8000
# or
openlcs/manage.py runserver host_server_ip:8000
```

Hint：If you run OpenLCS in remote server, need do the following steps:
- Change the `hostname` in `conf.cfg` to correct IP address
- Add `HOSTNAME(correct IP address)`, `REST_API_PATH` and `BROWSABLE_DOCUMENT_MACROS` in `settings_local.py`

```text
It can be accessed on http://localhost:8000/ or http://host_server_ip:8000/.
You can log in by going to http://127.0.0.1:8000/admin/login/ or http://host_server_ip:8000/admin/login/,
and using the account you set up in the previous section (user `admin`, password `test`).
You can check the restful API by going to http://127.0.0.1:8000/rest/v1/ or http://host_server_ip:8000/rest/v1/,
but need login to the server firstly.
```

### Running OpenLCS worker
OpenLCS worker can be started using the following (from the top directory of
the repo):
```shell
celery -A openlcsd worker --loglevel=INFO -Q celery,celery:1,celery:2 -Ofair --prefetch-multiplier=1
# If you want to debug using celery log, use:
celery -A openlcsd worker --loglevel=DEBUG -Q celery,celery:1,celery:2 -Ofair --prefetch-multiplier=1
```

### Running OpenLCS beat service
OpenLCS beat service can be started using the following (from the top directory of
the repo):
```shell
cd openlcs && celery -A openlcs beat --loglevel=INFO
```

Hint: You can remove all currently queued tasks using `redis-cli FLUSHALL`.


### How to add unit test cases for OpenLCS
```text
For Django app, add test cases in tests.py.
For lib in Django, add test cases in tests.py.
For workflow in openlcsd/flow/tasks.py, write test files in tests,
and add test file in suite defined in __init__.py
```

### OIDC setting
#### Set the following environment variables
```shell
# OIDC settings
export OIDC_AUTH_URI='xxx'
export OPENLCS_OIDC_RP_CLIENT_ID="xxx"
export OPENLCS_OIDC_RP_CLIENT_SECRET="xxx"
export USER_OIDC_CLIENT_ID="xxx"
export USER_OIDC_CLIENT_SECRET="xxx"
export OPENLCS_OIDC_AUTH_ENABLED="xxx"
export TOKEN_SECRET_KEY="xxx"
```

#### Set the following environment variables in the local settings
```shell
# Setting OIDC login and logout URLs.
OIDC_AUTH_URI = xxx
LOGIN_REDIRECT_URL = xxx
LOGIN_REDIRECT_URL_FAILURE = xxx
LOGOUT_REDIRECT_URL = xxx
```

#### Set autobot_token_file in conf.cfg
```shell
autobot_token_file = xxx(SRC_ROOT_DIR) + autobot_token_file
```

#### How to authentication
Project GUI use a "KERBEROS ID" and "PIN" + "OTP" to login, and user can get 
a project token from the url: /rest/v1/auth

Project commands will add this kerberos token in the header to authenticate, 
and according to this kerberos user's token to get the autobot user's token. In 
the internal fork tasks, will use the autobot user's token.