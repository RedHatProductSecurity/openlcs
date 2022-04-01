# SWH dev environment
```text
SWH provides a way to duplicate and store scanned software, but unfortunately 
this function in swh is not the main feature, Until now this function is still 
in internal testing status which is a potential risk for pelc2.

We should focus on bulk importing many archives to verify its stability, from 
my testing it seems some swh service will be dead or out of memory.

FYI we should not use a self-maintained SWH instance, we need to search for 
other ways to use SWH or drop this tool. Anyway need to come a conclusion ASAP
```


## SWH Instance info:
```text
Address: 10.0.211.248 , in openstack pelc-dev namespace
https://rhos-d.infra.prod.upshift.rdu2.redhat.com/dashboard/project/instances/

VM instance login account:  ubuntu/redhat  root/redhat
Note：
Use ubuntu account to login the server, 
If you want to use docker/docker-compose, change to root account

SWH web:
http://10.0.211.248:5080/  (admin/admin)

SWH deposit API:
http://10.0.211.248:5080/deposit/1  (test/test)

SWH rabbitmq web:
http://10.0.211.248:5080/rabbitmq (guest/guest)

SWH metrics:
http://10.0.211.248:5080/grafana (admin/admin) not start

SWH public project repo: 
https://forge.softwareheritage.org/source/swh-environment.git

Note: 
currently SWH use dev mode to deploy, the official provides a production way. 
From my point of view, it use puppet tool to deploy which is our not good at:
https://forge.softwareheritage.org/source/puppet-environment/ 
https://forge.softwareheritage.org/source/puppet-swh-site/
```

## Debug info:
### How to run SWH from scratch:
```text
Install docker and docker-compose service
```

```shell
# Clone repository
git clone https://forge.softwareheritage.org/source/swh-environment.git
```

```shell
# Install SWH config patches
cd swh-environment/docker
wget https://gitlab.cee.redhat.com/pelc/pelc2/-/raw/main/containers/docker-swh/conf-patches-install.sh --no-check-certificate
bash conf-patches-install.sh -w /home/ubuntu/swh-environment/docker
```

```shell
# Start SWH services
docker-compose up -d
```

```shell
# Install swh-loader-core.swh.loader.package.utils.py patch
wget https://gitlab.cee.redhat.com/pelc/pelc2/-/raw/main/containers/docker-swh/swh-loader-package-utils-patch-install.sh --no-check-certificate
bash swh-loader-package-utils-patch-install.sh
```


### Run and restart SWH
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
