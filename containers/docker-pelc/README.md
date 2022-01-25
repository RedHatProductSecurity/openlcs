## Docker-compose purpose is for local debug

### It's a mini pelc2 debug environment, for test related code 
```text
1. cd pelc2
# Default nginx port is 80 , gunicorn port is 8000, if your local 80/8000 port is occupied
# then change docker-compose file
2. docker-compose -f containers/docker-pelc/docker-compose.yml up
# If need running on backend, use this command
3. docker-compose -f containers/docker-pelc/docker-compose.yml up -d
```