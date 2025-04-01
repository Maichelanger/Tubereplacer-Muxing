#!/bin/bash
if ! test -f "./tuberepair/serverID.txt"; then
    pip3 install -r ./requirements.txt
    useradd tubeuser
    chown -R tubeuser:tubeuser ./tuberepair
fi
su tubeuser
cd ./tuberepair
echo 'Starting TubeRepair'
python3 ./main.py
