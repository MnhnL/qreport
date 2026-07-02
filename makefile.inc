## Variables needed in the including Makefile
# install_host: The host where the application is to be installed on
# app_name: The name of the application to be installed
# instance_name: The name of the instance to be installed, this is generally the main FQDN used and will be used in naming the systemd units and for variable data paths
# nginx_server_name: The server_name in the nginx file. This controls for what virtual host this site shall be served.

tmp_dir=/tmp/$(app_name)_$(instance_name)
python_sources := $(shell find $(app_name) -type f -name '*.py' -o -name '*.html' -o -name '*.css' -o -name '*.js')

ifeq ($(CLOBBER_NGINX_CONF), 1)
	mv_flags=
else
	mv_flags=-n
endif

.ONESHELL:

.PHONY: all
all:
	make build prepare update

# Download transitive dependencies of our package and put in
# dist/packages. This allows shipping the package with all dependencies
# and avoids any downloads during install on target.
.PHONY: transitive_dependencies
transitive_dependencies: dist/transitive_dependencies
dist/transitive_dependencies: requirements.txt
	rm -rf dist/packages
	mkdir -p dist/packages
	. venv/bin/activate
	python3 -m pip download -r requirements.txt -d dist/packages
	touch dist/transitive_dependencies

# Create the .whl package
.PHONY: build
build: dist/build
dist/build: $(python_sources) pyproject.toml dist/transitive_dependencies
	. venv/bin/activate
	python3 -m pip wheel . -w dist/packages
	touch dist/build

# Does the initial preparation and installation on server
.PHONY: prepare
prepare: dist/prepared
dist/prepared: dist/build
	ssh $(install_host) rm -rf $(tmp_dir)
	ssh $(install_host) mkdir $(tmp_dir)
	scp nginx.conf $(app_name)@.service $(install_host):$(tmp_dir)
	ssh $(install_host) "sudo bash -s $(app_name) $(instance_name) $(nginx_server_name) $(mv_flags)" < deploy_prepare.sh
	date > dist/prepared

# Install the package and transitive dependencies on the target machine, then restart
.PHONY: update
update: dist/prepared dist/build
	rsync -r dist/packages $(install_host):$(tmp_dir)/
	ssh $(install_host) "sudo bash -s $(app_name) $(instance_name) $(pip_args)" < deploy_update.sh
	$(MAKE) restart

# Restart the application service
.PHONY: restart
restart:
	ssh $(install_host) "sudo systemctl restart $(app_name)@$(instance_name).service"
