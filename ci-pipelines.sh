#!/bin/bash

set -xe

git --version
git status
git submodule update --init
git clone https://github.com/awslabs/git-secrets ./git-secrets
PATH=$PATH:./git-secrets git secrets --register-aws
if [[ "$1" =~ ^(stable|master|dev)$ ]]; then
    PATH=$PATH:./git-secrets git secrets --scan-history
else
    PATH=$PATH:./git-secrets git secrets --scan
fi
tox --version
cp -vf config.yml.sample config.yml
cp -vf web_ui/config.yml.sample web_ui/config.yml
tox
