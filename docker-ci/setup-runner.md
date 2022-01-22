## Gitlab runner service

### Currently pelc have two server 
```text
10.0.209.60 shell runner which is used for build image jobs
10.0.209.220 docker runner which is used for run jobs
```


### How to set up gitlab runner instance
1. Create a fedora instance in openstack, recommend size is 8core 16Gram 100Gdisk 
2. Login in to that server and then execute below script 
```bash
sudo su
# Install docker engine https://docs.docker.com/engine/install/fedora/
dnf -y install dnf-plugins-core vim
dnf config-manager     --add-repo     https://download.docker.com/linux/fedora/docker-ce.repo
dnf install docker-ce docker-ce-cli containerd.io

# Install gitlab runner https://docs.gitlab.com/runner/install/linux-manually.html
curl -LJO "https://gitlab-runner-downloads.s3.amazonaws.com/latest/rpm/gitlab-runner_amd64.rpm"
yum localinstall gitlab-runner_amd64.rpm -y

# https://docs.gitlab.com/runner/executors/shell.html
usermod -aG docker gitlab-runner

# start docker service 
systemctl start docker
systemctl enable docker

# Trust redhat certificate
cd /etc/pki/ca-trust/source/anchors/ && \
curl -skO https://password.corp.redhat.com/RH-IT-Root-CA.crt && \
curl -skO https://engineering.redhat.com/Eng-CA.crt && \
update-ca-trust && \
cd -

systemctl start gitlab-runner
systemctl enable gitlab-runner

# register runner https://gitlab.cee.redhat.com/pelc/pelc2/-/settings/ci_cd
gitlab-runner register
# Input your runner URL, description, tags, and executor type
# For docker type input docker, shell type input shell
# tags is used by .gitlabci

# Install cronjob to clear docker cache every 15 days
dnf install cronie
systemctl enable crond.service --now
echo "* * */15 * * docker image prune -a -f" >> /etc/crontab
```
