#!/usr/bin/env bash

SetWorkDir() {
    cd "$(dirname "$0")"/../../ || exit
}

RemoveServices() {
    docker rm -f $(docker ps -f "name=docker-openlcs" -q) > /dev/null 2>&1
    docker rmi -f $(docker images -f reference='quay.io/pelc/*:latest' -f reference='local/openlcs:latest' -q) > /dev/null 2>&1
}

UpdateCode() {
  current_branch="$(git branch --show-current)"
  if [[ "X${current_branch}" == "Xmain" ]]; then
    git pull
  fi
}

CreateStartServices() {
    docker-compose -f containers/docker-openlcs/docker-compose.yml up -d
}

UpdateDatabase() {
    docker exec docker-openlcs_gunicorn_1 bash -c "openlcs/manage.py migrate --noinput;
        export DJANGO_SUPERUSER_PASSWORD=test;
        openlcs/manage.py createsuperuser --username admin --noinput --email admin@test.com"
}

Help() {
    echo "Usage: bash containers/docker-openlcs/start-services.sh"
    echo "    This script will create and run OpenLCS services."
    echo ""
    echo "How to use:"
    echo "    Backend: http://host_server_ip:8000/admin/"
    echo "    Restful: http://host_server_ip:8000/rest/v1/"
    echo '    Default username is "admin", password is "test"'
}

main() {
    echo "Set work directory."
    SetWorkDir

    echo "Removing services in currently environment ..."
    RemoveServices

    echo "Updating project code ..."
    UpdateCode

    echo "Creating and starting new services ..."
    CreateStartServices

    echo "Updating project database ..."
    UpdateDatabase

    echo "Successfully start docker environment for OpenLCS."
}

if [[ $# != 0 ]]; then
    for arg in "$@"; do
        if [[ "X${arg}" =~ "X-h" || "X${arg}" =~ "X--help" ]]; then
            Help
            exit 0
        fi
    done
fi
main
