# swh-loader-package-utils.path
```text
This is a path for swh loader, it will extend timeout for loader source.
default is 60s, but if we deposit large source tarball, will cause timeout 
issue, so extend this timeout setting to 600s
```

## How to install this patch
### Get the patch
```shell
ssh ubuntu@10.0.211.248
sudo su - root
cd /home/ubuntu/swh-environment/docker
wget https://gitlab.cee.redhat.com/pelc/pelc2/-/raw/main/containers/patches/swh-loader-package-utils.patch
```

### Install the patch
This should be run after `docker-compose up -d`, so that the service "docker_swh-loader_1" exist and up
```shell
docker cp swh-loader-package-utils.patch docker_swh-loader_1:/srv/softwareheritage/venv/lib/python3.7/site-packages/swh/loader/package/swh-loader-package-utils.patch
docker exec docker_swh-loader_1 bash -c "cd /srv/softwareheritage/venv/lib/python3.7/site-packages/swh/loader/package/;patch < swh-loader-package-utils.patch"
```

### Restart all swh services
```shell
docker-compose restart
```