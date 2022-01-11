FROM registry.access.redhat.com/ubi8/python-38:1-75

MAINTAINER Xubiao Yao <xyao@redhat.com>

USER root

RUN cd /etc/pki/ca-trust/source/anchors/ && \
    curl -skO https://password.corp.redhat.com/RH-IT-Root-CA.crt && \
    curl -skO https://engineering.redhat.com/Eng-CA.crt && \
    update-ca-trust

RUN yum install --nogpgcheck -y \
    skopeo \
    && yum clean all

RUN git clone https://gitlab.cee.redhat.com/pelc/pelc2.git && \
    pip install --upgrade 'pip==21.3.1' && \
    pip install -r pelc2/requirements/devel.txt && \
    rm -rf pelc2

ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
ENV HOME=/home/pelc

RUN mkdir -p ${HOME} && \
    chmod a+rwX -R ${HOME}

# This download url is from currently ocp cluster console
RUN wget https://downloads-openshift-console.apps.ocp-c1.prod.psi.redhat.com/amd64/linux/oc.tar && \
    tar xf oc.tar -C /usr/local/bin/

WORKDIR /home/pelc
USER 1001