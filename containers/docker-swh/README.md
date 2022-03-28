# swh dev environment
```text
SWH provides a way to duplicate and store scanned software, but unfortunately 
this function in swh is not the main feature, Until now this function is still 
in internal testing status which is a potential risk for pelc2.

We should focus on bulk importing many archives to verify its stability, from 
my testing it seems some swh service will be dead or out of memory.

FYI we should not use a self-maintained SWH instance, we need to search for 
other ways to use SWH or drop this tool. Anyway need to come a conclusion ASAP
```


## Instance info:
```text
Address: 10.0.211.248 , in openstack pelc-dev namespace
https://rhos-d.infra.prod.upshift.rdu2.redhat.com/dashboard/project/instances/

Vm instance login account: ubuntu/redhat
Swh web login account: admin/admin
Swh deposit login account: test/test

Swh public project address: 
https://forge.softwareheritage.org/source/swh-environment.git

Note: 
currently swh use dev mode to deploy, the official provides a production way. 
From my point of view, it use puppet tool to deploy which is our not good at:
https://forge.softwareheritage.org/source/puppet-environment/ 
https://forge.softwareheritage.org/source/puppet-swh-site/
```


## Debug info:
### How to run swh from scratch:
```text
Install docker and docker-compose service
```

```shell
# Clone repository
git clone https://forge.softwareheritage.org/source/swh-environment.git
```

```shell
# Install swh config patches
cd swh-environmen/docker
wget https://gitlab.cee.redhat.com/pelc/pelc2/-/raw/main/containers/docker-swh/conf-patches-install.sh --no-check-certificate
bash conf-patches-install.sh
```

```shell
# Start swh services
docker-compose up -d
```

```shell
# Install swh.swh.loader.package.utils.py patch
wget https://gitlab.cee.redhat.com/pelc/pelc2/-/raw/main/containers/docker-swh/swh-loader-package-utils-patch-install.sh --no-check-certificate
bash swh-loader-package-utils-patch-install.sh
```


### Run and restart swh
```text
cd /home/ubuntu/swh-environment/docker
docker-compose up -d (run)
docker-compose down (stop)
docker-compose restart (restart)
```

### Monitor
```shell
docker stats
docker ps -a
docker-compose logs swh-loader-deposit
docker-compose logs swh-loader-deposit | grep -v succeeded | grep -v received(check failed task)
```
