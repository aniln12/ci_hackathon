#!/bin/bash

apt install -y uwsgi-plugin-python python-flask python-sqlalchemy python-psycopg2

cp ci_hackathon-master/backend/conservationintl.ini /etc/uwsgi/apps-enabled/
cp ci_hackathon-master/backend/nginx-site.conf /etc/nginx/sites-enabled/default

systemctl restart nginx
systemctl restart uwsgi

