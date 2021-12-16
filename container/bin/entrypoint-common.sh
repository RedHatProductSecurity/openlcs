cd /code

echo "default:x:$(id -u):0:Default user:/home/pelc/:/sbin/nologin" >> /etc/passwd
