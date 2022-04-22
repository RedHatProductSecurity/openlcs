## Gitlab runner service

### Currently, PELC has two gitlab runner services
Create fedora instances in openstack, recommend size is 8core 16G ram 100G disk 
1) 10.0.209.60  gitlab shell runner which is used for build image jobs
2) 10.0.209.220 gitlab docker runner which is used for run jobs

### How to set up gitlab runner instance
#### Trust redhat certificate
```shell
cd /etc/pki/ca-trust/source/anchors/ && \
curl -skO https://password.corp.redhat.com/RH-IT-Root-CA.crt && \
curl -skO https://engineering.redhat.com/Eng-CA.crt  && \
update-ca-trust && \
cd -
```

### Fedora Shell runner
```shell
# 1) Docker setting
# Install Docker Engine on RHEL https://docs.docker.com/engine/install/fedora/
# Uninstall old versions
sudo dnf remove docker \
                docker-client \
                docker-client-latest \
                docker-common \
                docker-latest \
                docker-latest-logrotate \
                docker-logrotate \
                docker-selinux \
                docker-engine-selinux \
                docker-engine
 
# Set up the repository
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
 
# Install Docker Engine
sudo dnf -y install docker-ce docker-ce-cli containerd.io

# Start docker service 
systemctl enable docker --now
```

```shell
# 2) Gitlab runner setting
# Install GitLab Runner manually on GNU/Linux https://docs.gitlab.com/runner/install/linux-manually.html
curl -LJO "https://gitlab-runner-downloads.s3.amazonaws.com/latest/rpm/gitlab-runner_amd64.rpm"
yum localinstall gitlab-runner_amd64.rpm -y

# Start gitlab-runner service
systemctl enable gitlab-runner --now

# Add gitlab-runner user to docker group https://docs.gitlab.com/runner/executors/shell.html
usermod -aG docker gitlab-runner
# if group "docker" exist, using command "sudo gpasswd -a gitlab-runner docker"
sudo systemctl restart gitlab-runner

# Register Shell runner https://docs.gitlab.com/runner/register/index.html#linux
# "URL" and "PROJECT_REGISTRATION_TOKEN" come from "Runners" in https://gitlab.cee.redhat.com/pelc/openlcs/-/settings/ci_cd
sudo gitlab-runner register \
  --non-interactive \
  --url "URL" \
  --registration-token "PROJECT_REGISTRATION_TOKEN" \
  --executor "shell" \
  --description "pelc-shell-runner" \
  --tag-list "pelc-shell-runner" \
  --run-untagged="true" \
  --locked="false" \
  --access-level="not_protected"
```

```shell
# 3) Cronjob setting
# Install cronjob to clear docker cache every 15 days
sudo yum -y install cronie
systemctl enable crond.service --now
echo "* * */15 * * docker image prune -a -f" >> /etc/crontab
```

```shell
# 4) gitlab pipeline setting
# Install skopeo
yum -y install skopeo
```

#### RHEL Docker runner
```shell
# 1) Docker setting
# Install Docker Engine on RHEL https://docs.docker.com/engine/install/rhel/
# Uninstall old versions
sudo yum remove docker \
                docker-client \
                docker-client-latest \
                docker-common \
                docker-latest \
                docker-latest-logrotate \
                docker-logrotate \
                docker-engine \
                podman \
                runc
 
# Set up the repository
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
 
# Install Docker Engine
sudo yum -y install docker-ce docker-ce-cli containerd.io

# Start docker service 
systemctl enable docker --now
```

```shell
# 2) Gitlab runner setting
# Install GitLab Runner manually on GNU/Linux https://docs.gitlab.com/runner/install/linux-manually.html
curl -LJO "https://gitlab-runner-downloads.s3.amazonaws.com/latest/rpm/gitlab-runner_amd64.rpm"
yum localinstall gitlab-runner_amd64.rpm -y

# Start gitlab-runner service
systemctl enable gitlab-runner --now

# Register Docker runner https://docs.gitlab.com/runner/register/index.html#linux
# "URL" and "PROJECT_REGISTRATION_TOKEN" come from "Runners" in https://gitlab.cee.redhat.com/pelc/openlcs/-/settings/ci_cd
sudo gitlab-runner register \
  --non-interactive \
  --url "URL" \
  --registration-token "PROJECT_REGISTRATION_TOKEN" \
  --executor "docker" \
  --docker-image alpine:latest \
  --description "pelc-docker-runner" \
  --tag-list "pelc-docker-runner" \
  --run-untagged="true" \
  --locked="false" \
  --access-level="not_protected"
```

```shell
# 3) Cronjob setting
# Install cronjob to clear docker cache every 15 days
sudo yum -y install cronie
systemctl enable crond.service --now
echo "* * */15 * * docker image prune -a -f" >> /etc/crontab
```

### Hint:
Use different "Docker setting" and "Gitlab runner setting" on different systems with different gitlab runners.
