# https://github.com/benoitc/gunicorn/blob/master/examples/example_config.py
# https://docs.gunicorn.org/en/stable/configure.html
import multiprocessing

bind = '0.0.0.0:8000'
chdir = 'pelc'
workers = multiprocessing.cpu_count() * 2 + 1
timeout = '600'
loglevel = 'info'
worker_classes = 'gevent'

# loglevel = 'debug' # in development uncomment below lines
# reload = true
