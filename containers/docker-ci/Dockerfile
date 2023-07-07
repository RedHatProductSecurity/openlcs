FROM registry.access.redhat.com/ubi8/python-38

ARG PRODSEC_DEV_OPENLCS_MAIL
ARG ROOT_CA_URL
ARG ENG_CA_URL
ARG TITO_REPO_URL
ARG RHEL8_REPO_URL
ARG RHEL8_APPSTREAM_REPO_URL
ARG OPENSHIFT_CLI_URL
ARG CORGI_API_STAGE
ARG CORGI_API_PROD
ARG KOJI_WEBSERVICE
ARG KOJI_WEBURL
ARG KOJI_DOWNLOAD
ARG LOOKASIDE_CACHE_URL
ARG OIDC_AUTH_URI
ARG OPENLCS_OIDC_RP_CLIENT_ID
ARG OPENLCS_OIDC_RP_CLIENT_SECRET
ARG USER_OIDC_CLIENT_ID
ARG USER_OIDC_CLIENT_SECRET
ARG OPENLCS_OIDC_AUTH_ENABLED
ARG TOKEN_SECRET_KEY

ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt \
    CORGI_API_STAGE=${CORGI_API_STAGE} \
    CORGI_API_PROD=${CORGI_API_PROD} \
    KOJI_WEBSERVICE=${KOJI_WEBSERVICE} \
    KOJI_WEBURL=${KOJI_WEBURL} \
    KOJI_DOWNLOAD=${KOJI_DOWNLOAD} \
    LOOKASIDE_CACHE_URL=${LOOKASIDE_CACHE_URL} \
    OIDC_AUTH_URI=${OIDC_AUTH_URI} \
    OPENLCS_OIDC_RP_CLIENT_ID=${OPENLCS_OIDC_RP_CLIENT_ID} \
    OPENLCS_OIDC_RP_CLIENT_SECRET=${OPENLCS_OIDC_RP_CLIENT_SECRET} \
    USER_OIDC_CLIENT_ID=${USER_OIDC_CLIENT_ID} \
    USER_OIDC_CLIENT_SECRET=${USER_OIDC_CLIENT_SECRET} \
    OPENLCS_OIDC_AUTH_ENABLED=${OPENLCS_OIDC_AUTH_ENABLED} \
    TOKEN_SECRET_KEY=${TOKEN_SECRET_KEY}

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
    dnf -y upgrade && \
    dnf config-manager --add-repo "${TITO_REPO_URL}" \
        --add-repo "${RHEL8_REPO_URL}" \
        --add-repo "${RHEL8_APPSTREAM_REPO_URL}" && \
    dnf install --nogpgcheck --nodoc -y cpio-2.12 atool-0.39.0 && \
    # Remove it caused by vulnerabilities CVE-2021-33503 and CVE-2020-26137
    dnf remove python2-urllib3 && \
    dnf clean all && \
    # To make docker cache pip package, install dependencies
    pip install --upgrade pip && pip install -r /tmp/devel.txt --use-pep517 && \
    # This download url is from currently ocp cluster console
    curl -k "${OPENSHIFT_CLI_URL}" | tar xf - -C /usr/local/bin/ && \
    # Link the site-packages to correct location, so that tox can find it when use current-env plugin
    # CI image site packages path is /usr/local/lib/python3.8/site-packages.
    # But tox will use one of ['/usr/local/lib64/python3.8/site-packages',
    # '/usr/local/lib/python3.8/site-packages', '/usr/lib64/python3.8/site-packages',
    # '/usr/lib/python3.8/site-packages'] as site packages path
    mkdir -p /usr/local/lib64/python3.8/ && \
    ln -s /opt/app-root/lib64/python3.8/site-packages /usr/local/lib64/python3.8/

# Apply patches for extractcode, packagedcode
COPY ./containers/patches/* /opt/app-root/lib64/python3.8/site-packages/
WORKDIR /opt/app-root/lib64/python3.8/site-packages/
RUN patch -p0 < extract.patch && \
    patch -p0 < rpm.patch

WORKDIR /opt/app-root/src
USER 1001
# To avoid docker cache invaild , put this in the last
ARG quay_expiration
LABEL quay.expires-after=$quay_expiration
