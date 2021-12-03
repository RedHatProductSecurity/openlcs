FROM registry.access.redhat.com/ubi8/python-36:1-159

MAINTAINER xubiao yao <xyao@redhat.com>

USER root

RUN pip install --upgrade 'pip==21.3.1'
# Install from pip, because the RPM one is not compatible with current pip
RUN pip install 'tox==3.24.4' \
    'flake8==4.0.1' \
    'pylint==2.12.2' \
    'pylint-django==2.4.4' \
    'pytest==6.2.5'

RUN cd /etc/pki/ca-trust/source/anchors/ && \
    curl -skO https://password.corp.redhat.com/RH-IT-Root-CA.crt && \
    curl -skO https://engineering.redhat.com/Eng-CA.crt && \
    update-ca-trust

# This download url is from currently ocp cluster console
RUN wget https://downloads-openshift-console.apps.ocp-c1.prod.psi.redhat.com/amd64/linux/oc.tar && \
tar xf oc.tar -C /usr/local/bin/

ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
ENV HOME=/home/pelc
WORKDIR /home/pelc
USER 1001