#!/bin/sh
. ../venv/bin/activate
export FLASK_ENV=production 
export WEBSERVER_PORT=5001
python daemon.py arch
