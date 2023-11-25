#!/bin/sh

if [ ! -f ./conf/conf.py ]; then
    cp ./conf/conf_dev.py ./conf/conf.py
fi

python3 ./main.py
