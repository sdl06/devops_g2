#!/bin/sh
set -e

flask --app split_app db upgrade
exec gunicorn --bind 0.0.0.0:8001 --access-logfile - wsgi:app
