## Gitlab runner service

### Currently, OpenLCS has two gitlab runners on RedHat openstack:
1) pelc-gitlab-shell-runner, which is used for build image jobs
2) pelc-gitlab-docker-runner, which is used for other CI/CD jobs

### How to set up a gitlab runner instance
#### Get RedHat certificate and update trust
```shell
cd /etc/pki/ca-trust/source/anchors/ && \
curl -O "${ROOT_CA_URL}" && \
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
# "PROJECT_REGISTRATION_TOKEN" are from "Runners" in project CI/CD settings.Click the 3 dot
# button next to "New project runner"
# "URL" If your project is hosted on gitlab.example.com/yourname/yourproject, 
# your GitLab instance URL is https://gitlab.example.com 
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
# 4) Gitlab pipeline setting
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
# "URL" and "PROJECT_REGISTRATION_TOKEN" are from "Runners" in project CI/CD settings
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
