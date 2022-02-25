#FROM registry.access.redhat.com/ubi8/python-38:1-75
# This image is copied from the first image, to prevent upstream image changed
FROM quay.io/pelc/python-38:latest

MAINTAINER Xubiao Yao <xyao@redhat.com>
LABEL name="pelc2-ci" \
      description="PELC2 ci-cd service in a container , will be auto deleted after 1 day"

USER root

RUN cd /etc/pki/ca-trust/source/anchors/ && \
    curl -skO https://password.corp.redhat.com/RH-IT-Root-CA.crt && \
    curl -skO https://engineering.redhat.com/Eng-CA.crt && \
    update-ca-trust

RUN dnf config-manager --add-repo http://tito.eng.nay.redhat.com/yum/redhat/pelc/qe/rhel8/noarch \
    --add-repo http://download.eng.bos.redhat.com/brewroot/repos/brew-rhel-8/latest/x86_64/ && \
    dnf install --nogpgcheck --nodoc -y  \
    cpio \
    atool && \
    dnf clean all

# This download url is from currently ocp cluster console
RUN curl -k  https://downloads-openshift-console.apps.ocp-c1.prod.psi.redhat.com/amd64/linux/oc.tar | tar xf - -C /usr/local/bin/

ADD ./requirements /tmp
RUN pip install --upgrade pip && pip install -r /tmp/devel.txt

ADD ./containers/patches/magic2.patch /opt/app-root/lib64/python3.8/site-packages/typecode
RUN cd /opt/app-root/lib64/python3.8/site-packages/typecode && patch < magic2.patch

# Link the site-packages to correct location, so that tox can find it when use current-env plugin
# CI image site packages path is /usr/local/lib/python3.8/site-packages.
# But tox will use one of ['/usr/local/lib64/python3.8/site-packages',
# '/usr/local/lib/python3.8/site-packages', '/usr/lib64/python3.8/site-packages',
# '/usr/lib/python3.8/site-packages'] as site packages path
RUN mkdir -p /usr/local/lib64/python3.8/ && \
    ln -s /opt/app-root/lib64/python3.8/site-packages /usr/local/lib64/python3.8/

WORKDIR /opt/app-root/src
USER 1001

# To avoid docker cache invaild , put this in the last
ARG quay_expiration
LABEL quay.expires-after=$quay_expiration
ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt