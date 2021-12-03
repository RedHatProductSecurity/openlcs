Celery service configuration

### Configure Celery configuration file
```shell
sudo mkdir /etc/conf.d
sudo cp celery /etc/conf.d/celery
```

### Create Celery user
```shell
sudo bash celery_user_configure -u celery -g celery
```

### Create Celery working directories
```shell
sudo cp celery.conf /etc/tmpfiles.d/celery.conf
sudo systemd-tmpfiles --create
```
Hint: Run `systemd-tmpfiles --create` to automatically create directories 
(only manually created, and files will be automatically created after startup)

### Configure Celery service file
```shell
sudo cp celery.service /etc/systemd/system/celery.service
```

### Enable Celery service
```shell
sudo systemctl daemon-reload
sudo systemctl enable celery.service
```

Hint: Once you’ve put that file in /etc/systemd/system, you should run 
`systemctl daemon-reload `in order that Systemd acknowledges that file. 
You should also run that command each time you modify it. 
Use `systemctl enable celery.service`, if you want the celery service to  
automatically start when (re)booting the system.

### Start Celery service
```shell
sudo systemctl start celery
```

### How to configure Celery service in local environment
```shell
# Change to your local Celery bin.
# /etc/conf.d/celery
# such as: CELERY_BIN="/home/chhan/.virtualenvs/pelc2/bin/celery"

# Create a unprivileged user, or use kerberos user
sudo bash celery_user_configure -u celery -g celery

# Change working directory as your project directory in your service
# /etc/systemd/system/celery.service
# such as: WorkingDirectory=/home/chhan/work/pelc2

# Enable Celery service
sudo systemctl daemon-reload
sudo systemctl enable celery.service

# Start your service
sudo systemctl start celery
```

Hint: If you don't want to use Celery service, run celery command directly.
`celery -A pelcd2 worker --loglevel=INFO` in project directory.

### How to test celery service
```shell
python ../tasks/test_result.py
```

#### How to debug service
```shell
sudo systemctl status celery.service
sudo journalctl -b -u celery
```