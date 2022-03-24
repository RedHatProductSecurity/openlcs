# https://catalog.redhat.com/software/containers/ubi8/python-38/5dde9cacbed8bd164a0af24a?container-tabs=overview
# FROM registry.access.redhat.com/ubi8/python-38:1-75
# This image is copied from the first image, to prevent upstream image changed
FROM quay.io/pelc/python-38:3.8.8

LABEL name="pelc2" \
      maintainer="prodsec-dev-pelc@redhat.com" \
      summary="PELC2" \
      description="PELC2 service in a container"

USER 0

# Copy sources from context
COPY ./requirements /tmp
COPY . /opt/app-root/src

# To avoid docker cache invaild , put these code in the last part
ARG quay_expiration
LABEL quay.expires-after=$quay_expiration
ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
ENV HOME=/opt/app-root/src
ENV PYTHONUNBUFFERED 1

RUN curl -sSk https://password.corp.redhat.com/RH-IT-Root-CA.crt \
        -o /etc/pki/ca-trust/source/anchors/Red_Hat_IT_Root_CA.crt && \
    curl -sSk https://engineering.redhat.com/Eng-CA.crt \
        -o /etc/pki/ca-trust/source/anchors/Eng-CA.crt && \
    update-ca-trust && \
    dnf config-manager --add-repo http://tito.eng.nay.redhat.com/yum/redhat/pelc/qe/rhel8/noarch \
        --add-repo http://download.eng.bos.redhat.com/brewroot/repos/brew-rhel-8/latest/x86_64/ && \
    dnf install --nogpgcheck --nodoc -y cpio-2.12 atool-0.39.0 && \
    dnf clean all && \
    # To make docker cache pip package, install dependencies
    pip install --upgrade pip && pip install -r /tmp/devel.txt && \
    # Add permissions for pelc
    mkdir -p /var/pelc/static /var/log/pelc/ /var/cache/ && \
    chmod a+rwX -R /var/log/pelc/ /var/cache/ /var/pelc/static "${HOME}" /etc/passwd && \
    chmod a+x -R "${HOME}"/containers/docker-pelc/bin/*

# Apply patch for typecode
COPY ./containers/patches/magic2.patch /opt/app-root/lib64/python3.8/site-packages/typecode
WORKDIR /opt/app-root/lib64/python3.8/site-packages/typecode
RUN patch < magic2.patch

# Apply patch for extractcode
COPY ./containers/patches/extract.patch /opt/app-root/lib64/python3.8/site-packages/extractcode
WORKDIR /opt/app-root/lib64/python3.8/site-packages/extractcode
RUN patch < extract.patch

WORKDIR "${HOME}"
USER 1001
