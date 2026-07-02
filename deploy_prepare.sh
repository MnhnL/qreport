#!/bin/bash
shopt -s nullglob

export app_name=$1
export instance_name=$2
export server_name=$3
mv_flags=$4

echo deploy_prepare $app_name, $instance_name, $server_name, $mv_flags

tmp_dir=/tmp/${app_name}_${instance_name}

# prepare application
echo "prepare application $app_name"
mkdir -p /usr/local/share/django/${app_name}
mv ${mv_flags} ${tmp_dir}/*.service /etc/systemd/system/

# prepare instance
echo "prepare instance $instance_name"
mkdir -p /usr/local/etc/django/${instance_name}
chgrp -R www-data /usr/local/etc/django/${instance_name}
chmod -R g+r,o-rwx /usr/local/etc/django/${instance_name}
envsubst '$instance_name $app_name $server_name' < ${tmp_dir}/nginx.conf > ${tmp_dir}/nginx.conf.subst
mv ${mv_flags} ${tmp_dir}/nginx.conf.subst /etc/nginx/sites-available/${instance_name}
systemctl daemon-reload
systemctl enable ${app_name}@${instance_name}.service
[[ ! -e /etc/nginx/sites-enabled/${instance_name} ]] && ln -s /etc/nginx/sites-{available,enabled}/${instance_name}
cd /usr/local/share/django/${app_name} && sudo python3 -m venv venv
