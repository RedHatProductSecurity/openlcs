# https://github.com/benoitc/gunicorn/blob/master/examples/example_config.py
# https://docs.gunicorn.org/en/stable/configure.html
# This configuration is for development

bind = '0.0.0.0:8000'
chdir = 'pelc'
# Auto-detect cpu number is invalid in container mode
# Need manually configure
# workers = multiprocessing.cpu_count() * 2 + 1
workers = 5
timeout = '36000'  # 10 hours timeout
loglevel = 'debug'
worker_classes = 'gevent'
reload = "true"
