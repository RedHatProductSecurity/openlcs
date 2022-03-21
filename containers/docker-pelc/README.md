## Docker-compose purpose is for local debug

### It's a mini pelc2 debug environment, for test related code 

## Prepare
```shell
cd pelc2
# Default gunicorn port is 8000, nginx port is 8001, 
# if your local 8000/8001 ports are occupied,
# change docker-compose.yml file and nginx.conf.
```

## Create services, and start services
```shell
docker-compose -f containers/docker-pelc/docker-compose.yml up

# If need running on backend, use this command
docker-compose -f containers/docker-pelc/docker-compose.yml up -d
```

## Debug
```shell
# Go to services
docker exec -it container_name /bin/bash

# Check the services log
docker logs container_name

# container_name should be one of "docker-pelc_nginx_1", 
# "docker-pelc_worker_1", "docker-pelc_gunicorn_1",
# "docker-pelc_postgresql_1", "docker-pelc_redis_1"

# rebuild services
docker rm -f `docker ps -a -q`
docker image rm -f `docker image ls -q`
docker-compose -f containers/docker-pelc/docker-compose.yml up -d

# Update database
docker exec -it docker-pelc_gunicorn_1 /bin/bash
pelc/manage.py migrate --noinput
export DJANGO_SUPERUSER_PASSWORD=test
pelc/manage.py createsuperuser --username admin --noinput --email admin@test.com

# How to use
# Backend: http://host_server_ip:8000/admin/
# Restful: http://host_server_ip:8000/rest/v1/
# Default username is "admin", password is "test"
```