#!/usr/bin/env bash

# We want the script to exit at the first encountered error
set -e
WORKDIR="${HOME}/swh-environment/docker"
TIMEOUT=600

SetWorkDir() {
    cd "${WORKDIR}" || exit
}

InstallSWHLoaderPackageUtilsPatch() {
    docker exec docker_swh-loader_1 bash -c "sed -ri \"/^[^#]/s/(^\s+timeout\s+=).*/\1 ${TIMEOUT}/\" /srv/softwareheritage/venv/lib/python3.7/site-packages/swh/loader/package/utils.py"
    docker exec docker_swh-loader-deposit_1 bash -c "sed -ri \"/^[^#]/s/(^\s+timeout\s+=).*/\1 ${TIMEOUT}/\" /srv/softwareheritage/venv/lib/python3.7/site-packages/swh/loader/package/utils.py"
    docker-compose restart
}

Help() {
    echo "Usage: bash swh-loader-package-utils-patch-install.sh [OPTIONS]"
    echo "This is a path for swh loader, it will extend timeout for loader source."
    echo "default is 60s, but if we deposit large source tarball, will cause timeout"
    echo "issue, so extend this timeout setting."
    echo ""
    echo "Options:"
    echo "  -h, --help      Display help text"
    echo "  -w, --work-dir  Set work directory that contain docker-compose.yml,"
    echo "                  default is ${HOME}/swh-environment/docker"
    echo "  -t, --timeout   Set loader timeout, default is 60s"
    echo ""
    echo "Example:"
    echo "bash swh-loader-package-utils-patch-install.sh -w /home/ubuntu/swh-environment/docker -t 600"
    echo ""
}

main() {
    echo "Set work directory."
    SetWorkDir

    echo "Start to install patch for swh.loader.package.utils.py ..."
    InstallSWHLoaderPackageUtilsPatch
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
            set_workdir=True
            continue
        fi
        if [[ "${arg}" = "-t" || "${arg}" = "--timeout" ]]; then
            set_timeout=True
            continue
        fi
        if [[ "${set_workdir}" = "True" ]]; then
            WORKDIR=${arg}
            set_workdir=False
        fi
        if [[ "${set_timeout}" = "True" ]]; then
            TIMEOUT=${arg}
            set_timeout=False
        fi
    done
fi

main
