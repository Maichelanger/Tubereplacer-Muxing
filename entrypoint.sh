#!/bin/sh
pip3 install -r ./requirements.txt
cd ./tuberepair
echo 'Starting TubeRepair'
python3 ./main.py
