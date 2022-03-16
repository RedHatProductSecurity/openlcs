## Docker-compose purpose is for local debug

### It's a mini pelc2 debug environment, for test related code 
```text
1. cd pelc2
# Default gunicorn port is 8000, nginx port is 8001, 
# if your local 8000/8001 ports are occupied,
# change docker-compose.yml file and nginx.conf.

2. docker-compose -f containers/docker-pelc/docker-compose.yml up

# If need running on backend, use this command
3. docker-compose -f containers/docker-pelc/docker-compose.yml up -d
```