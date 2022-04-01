#!/usr/bin/env bash

# We want the script to exit at the first encountered error
set -e
WORKDIR="${HOME}/swh-environment/docker"

SetWorkDir() {
    cd "${WORKDIR}" || exit
}

# Set max_upload_size to 20000000000
InstallSWHConfDepositPatch() {
    if grep -q "^max_upload_size" ./conf/deposit.yml; then
        if ! grep -q "^max_upload_size: 20000000000" ./conf/deposit.yml;then
            sed -ri '/^[^#]/s/(^max_upload_size:\s).*/\120000000000/' conf/deposit.yml
        fi
    else
        echo "max_upload_size: 20000000000" >> conf/deposit.yml
    fi
}

InstallSWHConfNginxPatch() {
    # http://nginx.org/en/docs/http/ngx_http_core_module.html
    HTTP_SETTINGS=$(sed -n '/http {/,/server {/p' conf/nginx.conf)

    # Set client_max_body_size to 20G
    if echo "$HTTP_SETTINGS"|grep -E -q "client_max_body_size"; then
        if ! echo "$HTTP_SETTINGS"|grep -E -q "^\s+client_max_body_size\s+20G"; then
            sed  -ri '/^http\s+\{/,/^\s+server\s+\{/s/(^\s+client_max_body_size\s+).*/\120G;/' conf/nginx.conf
        fi
    else
        sed  -ri '/^\s+server\s+\{/i\  proxy_connect_timeout 20G;' conf/nginx.conf
    fi
}

InstallSWHDockerComposePatch() {
    sed -ri '/^\s+prometheus:$/,/grafana\/dashboards"$/s/(.*)/#\1/' docker-compose.yml
}

Help() {
    echo "Usage: bash conf-patches-install.sh [OPTIONS]"
    echo "Install all the patches about swh server config."
    echo ""
    echo "Options:"
    echo "  -h, --help      Display help text"
    echo "  -w, --work-dir  Set work directory that contain docker-compose.yml,"
    echo "                  default is ${HOME}/swh-environment/docker"
    echo ""
    echo "Example:"
    echo "bash conf-patches-install.sh -w /home/ubuntu/swh-environment/docker"
    echo ""
}

main() {
    echo "Set work directory."
    SetWorkDir

    echo "Start to install swh-conf-deposit.patch ..."
    InstallSWHConfDepositPatch

    echo "Start to install swh-conf-nginx.path ..."
    InstallSWHConfNginxPatch

    echo "Start to install swh-docker-compose.path ..."
    InstallSWHDockerComposePatch

    echo "Successfully installed all swh config patch."
}

if [[ $# != 0 ]]; then
    for arg in "$@"; do
        if [[ "${arg}" = "-h" || "${arg}" = "--help" ]]; then
            Help
            exit 0
        fi
    done

    for arg in "$@"; do
        if [[ "${arg}" = "-w" || "${arg}" = "--work-dir" ]]; then
            set_work_dir=True
            continue
        fi
        if [ "${set_work_dir}" ]; then
            WORKDIR=${arg}
            break
        fi
    done
fi

main
