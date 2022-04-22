## Docker-compose purpose is for local debug

### It's a mini openlcs debug environment, for test related code 

## Prepare
```shell
cd openlcs
# Default gunicorn port is 8000, nginx port is 8001, 
# if your local 8000/8001 ports are occupied,
# change docker-compose.yml file and nginx.conf.
```

## Create services, and start services
```shell
# If you want to configure it later, you can use docker-compose.
docker-compose -f containers/docker-openlcs/docker-compose.yml up

# If need running on backend, use this command
docker-compose -f containers/docker-openlcs/docker-compose.yml up -d

# If you want to get environment with configured services, you can use this command
# it will remove existed images and containers of OpenLCS.
bash containers/docker-openlcs/start-services.sh
```

## Debug
```shell
# Go to services
docker exec -it container_name /bin/bash

# Check the services log
docker logs container_name

# container_name should be one of "docker-openlcs_nginx_1", 
# "docker-openlcs_worker_1", "docker-openlcs_gunicorn_1",
# "docker-openlcs_postgresql_1", "docker-openlcs_redis_1"

# rebuild services
docker rm -f $(docker ps -f "name=docker-openlcs" -q)
docker rmi -f $(docker images -f reference='quay.io/pelc/*:latest' -f reference='local/openlcs:latest' -q)
docker-compose -f containers/docker-openlcs/docker-compose.yml up -d

# Update database
docker exec -it docker-openlcs_gunicorn_1 /bin/bash
openlcs/manage.py migrate --noinput
export DJANGO_SUPERUSER_PASSWORD=test
openlcs/manage.py createsuperuser --username admin --noinput --email admin@test.com

# How to use
# Backend: http://host_server_ip:8000/admin/
# Restful: http://host_server_ip:8000/rest/v1/
# Default username is "admin", password is "test"
```
