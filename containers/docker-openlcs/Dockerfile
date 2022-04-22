# https://catalog.redhat.com/software/containers/ubi8/python-38/5dde9cacbed8bd164a0af24a?container-tabs=overview
# FROM registry.access.redhat.com/ubi8/python-38:1-75
# This image is copied from the first image, to prevent upstream image changed
FROM quay.io/pelc/python-38:3.8.8

LABEL name="openlcs" \
      maintainer="prodsec-dev-pelc@redhat.com" \
      summary="OpenLCS" \
      description="OpenLCS service in a container"

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
    # Add permissions for openlcs 
    mkdir -p /var/openlcs/static /var/log/openlcs/ /var/cache/ && \
    chmod a+rwX -R /var/log/openlcs/ /var/cache/ /var/openlcs/static "${HOME}" /etc/passwd && \
    chmod a+x -R "${HOME}"/containers/docker-openlcs/bin/*

# Apply patch for typecode, extractcode, packagedcode
COPY ./containers/patches/* /opt/app-root/lib64/python3.8/site-packages/
WORKDIR /opt/app-root/lib64/python3.8/site-packages/
RUN patch -p0 < magic2.patch && \
    patch -p0 < extract.patch && \
    patch -p0 < rpm.patch

WORKDIR "${HOME}"
USER 1001
