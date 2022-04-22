#!/bin/bash

echo "default:x:$(id -u):0:Default user:/opt/app-root/src:/sbin/nologin" >> /etc/passwd
