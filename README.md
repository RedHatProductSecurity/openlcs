# PELC2

The next generation of PELC

## Setting up development environment
This section assumes you're running sufficiently recent version of Fedora.

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

Hint: you can put `export PGDATABASE=pelc2` into your `.bashrc` and then you don't have to
specify `pelc2` as the database when using `psql`.