#!/bin/sh

cd ..

sudo rm -rf /usr/share/nginx/mock-project-01/web
sudo cp -rf ./web /usr/share/nginx/mock-project-01

sudo rm -rf /usr/share/nginx/mock-project-01/web/conf.*
sudo cp -rf ./web/conf.beta.js /usr/share/nginx/mock-project-01/web/conf.js
