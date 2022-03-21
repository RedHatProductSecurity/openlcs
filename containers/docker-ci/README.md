# How to update CI docker image

## Prepare
```shell
docker login quay.io
docker image rm -f `docker image ls quay.io/pelc/pelc2-ci:latest -q`
cd pelc2
cp containers/docker-ci/.dockerignore .
```

## Create local CI docker image
```shell
docker build --tag quay.io/pelc/pelc2-ci:latest -f containers/docker-ci/Dockerfile .
```

## Push the CI docker image to quay.io
```shell
docker push quay.io/pelc/pelc2-ci
```

## Remove .dockerignore
```shell
rm -f .dockerignore
```

## Test the CI docker image 
```text
Rerun pipeline to test it.
```

### Hint:
```text
It is better to create local CI docker in Openstack environment.
```
