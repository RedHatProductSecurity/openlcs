# https://catalog.redhat.com/software/containers/rhel8/nginx-118/5f521a46e05bbcd88f128b64?container-tabs=overview
# Part of this image is copied from registry.access.redhat.com/ubi8/nginx-118
# Because we need to install the module spnego-http-auth-nginx-module
FROM quay.io/pelc/s2i-core:1-310

EXPOSE 8080
EXPOSE 8443

ENV NAME=nginx \
    NGINX_VERSION=1.18 \
    NGINX_SHORT_VER=118 \
    VERSION=0

ENV SUMMARY="Platform for running nginx $NGINX_VERSION or building nginx-based application" \
    DESCRIPTION="Nginx is a web server and a reverse proxy server for HTTP, SMTP, POP3 and IMAP \
protocols, with a strong focus on high concurrency, performance and low memory usage. The container \
image provides a containerized packaging of the nginx $NGINX_VERSION daemon with module \
spnego-http-auth-nginx-module. The image can be used as a base image for other applications based \
on nginx $NGINX_VERSION web server."

LABEL summary="${SUMMARY}" \
      description="${DESCRIPTION}" \
      io.k8s.description="${DESCRIPTION}" \
      io.k8s.display-name="Nginx ${NGINX_VERSION}" \
      io.openshift.expose-services="8080:http" \
      io.openshift.expose-services="8443:https" \
      io.openshift.tags="builder,${NAME},${NAME}-${NGINX_SHORT_VER}" \
      com.redhat.component="${NAME}-${NGINX_SHORT_VER}-container" \
      name="${NAME}-${NGINX_SHORT_VER}" \
      version="1" \
      com.redhat.license_terms="https://www.redhat.com/en/about/red-hat-end-user-license-agreements#UBI" \
      maintainer="prodsec-dev-pelc@redhat.com" \
      help="For more information visit https://github.com/sclorg/${NAME}-container" \
      usage="s2i build <SOURCE-REPOSITORY> ubi8/${NAME}-${NGINX_SHORT_VER}:latest <APP-NAME>"

ENV NGINX_CONFIGURATION_PATH=${APP_ROOT}/etc/nginx.d \
    NGINX_CONF_PATH=/etc/nginx/nginx.conf \
    NGINX_DEFAULT_CONF_PATH=${APP_ROOT}/etc/nginx.default.d \
    NGINX_CONTAINER_SCRIPTS_PATH=/usr/share/container-scripts/nginx \
    NGINX_APP_ROOT=${APP_ROOT} \
    NGINX_LOG_PATH=/var/log/nginx \
    NGINX_PERL_MODULE_PATH=${APP_ROOT}/etc/perl

RUN curl -sSk https://password.corp.redhat.com/RH-IT-Root-CA.crt \
        -o /etc/pki/ca-trust/source/anchors/Red_Hat_IT_Root_CA.crt && \
    curl -sSk https://engineering.redhat.com/Eng-CA.crt \
        -o /etc/pki/ca-trust/source/anchors/Eng-CA.crt && \
    update-ca-trust && \
    dnf config-manager --add-repo http://download.eng.bos.redhat.com/brewroot/repos/brew-rhel-8/latest/x86_64/ && \
    # Install module spnego-http-auth-nginx-module
    yum -y install gcc gcc-c++ make pcre pcre-devel zlib zlib-devel openssl openssl-devel wget vim iproute krb5-workstation&& \
    wget https://github.com/stnoonan/spnego-http-auth-nginx-module/archive/refs/tags/v1.1.1.tar.gz && \
    mkdir spnego-http-auth-nginx-module && \
    # Install Nginx
    tar -zxf v1.1.1.tar.gz -C spnego-http-auth-nginx-module --strip-components=1 && \
    yum -y install gcc gcc-c++ make pcre pcre-devel  zlib zlib-devel  openssl && \
    groupadd -r nginx && \
    useradd -r -g nginx -M nginx && \
    wget https://nginx.org/download/nginx-1.18.0.tar.gz && \
    tar zxf nginx-1.18.0.tar.gz && \
    cd nginx-1.18.0 && \
    ./configure \
    --sbin-path=/usr/local/nginx/nginx \
    --conf-path=/usr/local/nginx/nginx.conf \
    --pid-path=/usr/local/nginx/nginx.pid \
    --with-pcre \
    --with-http_ssl_module \
    --with-stream \
    --with-mail=dynamic \
    --with-debug \
    --add-module=../spnego-http-auth-nginx-module && \
    make && \
    make install && \
    yum -y clean all --enablerepo='*' && \
    /usr/local/nginx/nginx -c /usr/local/nginx/nginx.conf && \
    /usr/local/nginx/nginx -s reload && \
    chown -R 1001:0 /usr/local/nginx && \
    chmod -R a+rwx /usr/local/nginx

USER 1001
