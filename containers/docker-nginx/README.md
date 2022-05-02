# How to update Nginx docker image

## Prepare
```shell
docker login quay.io
```

## s2i-core docker image
```shell
docker image rm -f `docker image ls registry.access.redhat.com/ubi8/s2i-core:1-310 -q`
docker image rm -f `docker image ls quay.io/pelc/s2i-core:1-310 -q`
docker pull registry.access.redhat.com/ubi8/s2i-core:1-310
docker image tag registry.access.redhat.com/ubi8/s2i-core:1-310 quay.io/pelc/s2i-core:1-310
doker push quay.io/pelc/s2i-core:1-310
```

## Nginx docker image
```shell
docker image rm -f `docker image ls quay.io/pelc/nginx-118:latest -q`
docker build --tag quay.io/pelc/nginx-118:latest -f containers/docker-nginx/Dockerfile .
docker push quay.io/pelc/nginx-118:latest
```

### Hint:
```text
It is better to operate docker in Openstack environment.
the startup file is /usr/local/nginx/nginx
config file is /usr/local/nginx/nginx.conf
```
