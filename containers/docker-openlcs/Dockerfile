# https://catalog.redhat.com/software/containers/ubi8/python-38/5dde9cacbed8bd164a0af24a?container-tabs=overview
# FROM registry.access.redhat.com/ubi8/python-38:1-75
FROM registry.access.redhat.com/ubi8/python-38

ARG PRODSEC_DEV_OPENLCS_MAIL
ARG ROOT_CA_URL
ARG ENG_CA_URL
ARG TITO_REPO_URL
ARG RHEL8_REPO_URL
ARG RHEL8_APPSTREAM_REPO_URL
ARG DOCKER_REPO_URL
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
ARG OPENLCS_ADMIN_LIST

LABEL name="openlcs" \
      maintainer="${PRODSEC_DEV_OPENLCS_MAIL}" \
      summary="OpenLCS" \
      description="OpenLCS service in a container"

USER 0

# Copy sources from context
COPY ./requirements /tmp
COPY . /opt/app-root/src

# To avoid docker cache invaild , put these code in the last part
ARG quay_expiration
LABEL quay.expires-after=$quay_expiration
ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt \
    HOME=/opt/app-root/src \
    PYTHONUNBUFFERED=1 \
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
    OPENLCS_ADMIN_LIST=${OPENLCS_ADMIN_LIST} \
    TOKEN_SECRET_KEY=${TOKEN_SECRET_KEY}

RUN cd /etc/pki/ca-trust/source/anchors/ && \
        curl -skO "${ROOT_CA_URL}" && \
        curl -skO "${ENG_CA_URL}" && \
        update-ca-trust && \
        cd - && \
    dnf -y upgrade && \
    dnf config-manager --add-repo "${TITO_REPO_URL}" \
        --add-repo "${RHEL8_REPO_URL}" \
        --add-repo "${RHEL8_APPSTREAM_REPO_URL}" \
        --add-repo "${DOCKER_REPO_URL}" && \
    dnf install --nogpgcheck --nodoc -y cpio-2.12 atool-0.39.0 vim docker-ce-cli skopeo && \
    dnf clean all && \
    # To make docker cache pip package, install dependencies
    pip install --upgrade pip && pip install --upgrade setuptools && pip install -r /tmp/base.txt --use-pep517 && \
    # Add permissions for openlcs
    mkdir -p /var/openlcs/static /var/log/openlcs/ /var/cache/ && \
    chmod a+rwX -R /var/log/openlcs/ /var/cache/ /var/openlcs/static "${HOME}" /etc/passwd && \
    chmod a+rwX -R /opt/app-root/lib64/python3.8/site-packages/ && \
    chown -R 1001:0 /opt/app-root/lib64/python3.8/site-packages/ && \
    chmod a+x -R "${HOME}"/containers/docker-openlcs/bin/* && \
    chown -R 1001:0 "${HOME}"

# Apply patches for extractcode, packagedcode
COPY ./containers/patches/* /opt/app-root/lib64/python3.8/site-packages/
WORKDIR /opt/app-root/lib64/python3.8/site-packages/
RUN patch -p0 < extract.patch && \
    patch -p0 < rpm.patch

WORKDIR "${HOME}"
USER 1001
