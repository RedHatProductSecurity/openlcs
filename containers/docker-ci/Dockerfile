FROM registry.access.redhat.com/ubi8/python-38:1-75

ARG PRODSEC_DEV_OPENLCS_MAIL
ARG ROOT_CA_URL
ARG ENG_CA_URL
ARG TITO_REPO_URL
ARG RHEL8_REPO_URL
ARG OPENSHIFT_CLI_URL
ARG CORGI_API_STAGE
ARG CORGI_API_PROD
ARG KOJI_WEBSERVICE
ARG KOJI_WEBURL
ARG KOJI_DOWNLOAD
ARG LDAP_URI

ENV CORGI_API_STAGE=${CORGI_API_STAGE}
ENV CORGI_API_PROD=${CORGI_API_PROD}
ENV KOJI_WEBSERVICE=${KOJI_WEBSERVICE}
ENV KOJI_WEBURL=${KOJI_WEBURL}
ENV KOJI_DOWNLOAD=${KOJI_DOWNLOAD}
ENV LDAP_URI=${LDAP_URI}

LABEL name="openlcs-ci" \
      maintainer="${PRODSEC_DEV_OPENLCS_MAIL}" \
      summary="OpenLCS CI/CD" \
      description="OpenLCS ci-cd service in a container, will be auto deleted after 1 day"

USER 0

COPY ./requirements /tmp

# Return error when each pipe failed
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN cd /etc/pki/ca-trust/source/anchors/ && \
        curl -skO "${ROOT_CA_URL}" && \
        curl -skO "${ENG_CA_URL}" && \
        update-ca-trust && \
        cd - && \
    dnf config-manager --add-repo "${TITO_REPO_URL}" \
        --add-repo "${RHEL8_REPO_URL}" && \
    dnf install --nogpgcheck --nodoc -y cpio-2.12 atool-0.39.0 && \
    dnf clean all && \
    # To make docker cache pip package, install dependencies
    pip install --upgrade pip && pip install -r /tmp/devel.txt && \
    # This download url is from currently ocp cluster console
    curl -k "${OPENSHIFT_CLI_URL}" | tar xf - -C /usr/local/bin/ && \
    pip install --upgrade pip && pip install -r /tmp/devel.txt && \
    # Link the site-packages to correct location, so that tox can find it when use current-env plugin
    # CI image site packages path is /usr/local/lib/python3.8/site-packages.
    # But tox will use one of ['/usr/local/lib64/python3.8/site-packages',
    # '/usr/local/lib/python3.8/site-packages', '/usr/lib64/python3.8/site-packages',
    # '/usr/lib/python3.8/site-packages'] as site packages path
    mkdir -p /usr/local/lib64/python3.8/ && \
    ln -s /opt/app-root/lib64/python3.8/site-packages /usr/local/lib64/python3.8/

# Apply patch for typecode, extractcode, packagedcode
COPY ./containers/patches/* /opt/app-root/lib64/python3.8/site-packages/
WORKDIR /opt/app-root/lib64/python3.8/site-packages/
RUN patch -p0 < magic2.patch && \
    patch -p0 < extract.patch && \
    patch -p0 < rpm.patch

WORKDIR /opt/app-root/src
USER 1001

# To avoid docker cache invaild , put this in the last
ARG quay_expiration
LABEL quay.expires-after=$quay_expiration
ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
