# How to update CI docker image

## Copy Dockerfile
Ｃopy the latest Dockerfile to docker environment.

## Create local CI docker image
```shell
docker build --tag quay.io/pelc/pelc2-ci:latest .
```

## Push the CI docker image to quay.io
```shell
docker push quay.io/pelc/pelc2-ci
```

## Test the CI docker image 
Rerun pipeline to test it.


### Hint:
It is better to create local CI docker in Openstack environment.

If you need to add new library to requirements, merge it first, then update CI docker image.