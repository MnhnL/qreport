#!/bin/bash

app_name=$1
instance_name=$2
pip_args=$3

tmp_dir=/tmp/${app_name}_${instance_name}

cd /usr/local/share/django/${app_name}/
source venv/bin/activate
python3 -m pip install ${pip_args} --force-reinstall --find-links ${tmp_dir}/packages ${app_name}
deactivate
