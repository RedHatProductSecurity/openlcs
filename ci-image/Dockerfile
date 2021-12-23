FROM registry.access.redhat.com/ubi8/python-38:1-75

MAINTAINER xubiao yao <xyao@redhat.com>

USER root

RUN cd /etc/pki/ca-trust/source/anchors/ && \
    curl -skO https://password.corp.redhat.com/RH-IT-Root-CA.crt && \
    curl -skO https://engineering.redhat.com/Eng-CA.crt && \
    update-ca-trust

RUN git clone https://gitlab.cee.redhat.com/pelc/pelc2.git && \
    pip install --upgrade 'pip==21.3.1' && \
    pip install -r pelc2/requirements/devel.txt && \
    rm -rf pelc2

# This download url is from currently ocp cluster console
RUN wget https://downloads-openshift-console.apps.ocp-c1.prod.psi.redhat.com/amd64/linux/oc.tar && \
tar xf oc.tar -C /usr/local/bin/

ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
ENV HOME=/home/pelc
WORKDIR /home/pelc
USER 1001