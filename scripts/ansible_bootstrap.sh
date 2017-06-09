#!/bin/bash
set -xe

info() {
    if type uname >/dev/null 2>&1; then
        info_arch
        info_system 
    else
        echo "Error: needs \"uname\" command to work"
        exit 1
    fi
    echo -e "OS ARCH:\t $OS_ARCH"
    echo -e "OS NAME:\t $OS_NAME"
    echo -e "DISTRO NAME:\t $DISTRO_NAME"
}

info_arch() {
    OS_ARCH=$(uname -m 2>/dev/null)
}

info_system() {
    OS_NAME=$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')
    case ${OS_NAME} in
        linux )
            info_distro
            ;;
        * )
            echo "Error: ${OS_NAME} not supported"
            exit 1
            ;;
    esac
}

info_distro() {
    release_file="/etc/os-release"
    distro_file=$(find /etc/ -mindepth 1 -maxdepth 1 -type f \( -name '*[_-]release' -o -name '*[_-]version' \) | grep -v 'os-release' | head -n 1)
    if type lsb_release >/dev/null 2>&1; then
        DISTRO_NAME=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
    elif [ -f $release_file ]; then
        grep "^NAME=" ${release_file} | tr '[:upper:]' '[:lower:]' | sed 's/name=/DISTRO_NAME=/' | awk '{print $1}' > /tmp/distro_info
        echo $DISTRO_NAME
        grep "^VERSION_ID=" ${release_file} | sed 's/VERSION_ID=/DISTRO_VERSION=/' >> /tmp/distro_info
        source /tmp/distro_info
    elif [ ! -z ${distro_file} ]; then
        DISTRO_NAME=$(basename ${distro_file} | sed -e 's/[_-]release$//' -e 's/[_-]version$//')
    elif type pip >/dev/null 2>&1; then
        PIP_INSTALL=1
    else
        echo "Error: impossible to find release information and pip is not available"
        exit 1
    fi
}

init() {
    case ${DISTRO_NAME} in
        "debian" | "ubuntu" )
            DISTRO_VERSION=$(lsb_release -sr | cut -d'.' -f1)
            DEBIAN_FRONTEND=noninteractive apt-get update -y
            DEBIAN_FRONTEND=noninteractive apt-get install -y python
            deb_old=0
            if [ ${DISTRO_NAME} == "debian" ]; then 
                if [ ${DISTRO_VERSION} -lt 8 ]; then
                    deb_old=1
                fi
            else
                if [ ${DISTRO_VERSION} -lt 14 ]; then 
                    deb_old=1
                fi
            fi
            if [ ${deb_old} -eq 1 ]; then
                init_deb_old
            else
                init_deb_new
            fi
            # Install ansible modules dependencies
            DEBIAN_FRONTEND=noninteractive apt-get install -y bzip2 file findutils git gzip mercurial procps subversion sudo tar debianutils unzip xz-utils zip python-selinux
            ;;
        "centos" | "scientific" | "redhat" )
            url="https://dl.fedoraproject.org/pub/epel/${el_version}/${OS_ARCH}"
            el_version=$(uname -r | sed 's/.*el\([0-9]\).*/\1/')
            if [ "${el_version}" == "7" ]; then
                url="${url}/e"
            fi
            epel_version=$(curl -s "${url}/" | grep epel-release | sed "s/.*epel-release-${el_version}-\([0-9]\).noarch.rpm.*/\1/")
            yum install -y epel-release ||
            rpm -Uvh "${url}/epel-release-${el_version}-${epel_version}.noarch.rpm"
            ;;
	* )
            if [ -z ${PIP_INSTALL} ]; then
                 echo "No need init for this distro"
            else
		 init_pip
            fi
    esac
}

init_deb_old() {
    DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential
    DEBIAN_FRONTEND=noninteractive apt-get install -y python-all-dev python-mysqldb sshpass libssl-dev libffi-dev python-pip python-jinja2 python-httplib2 python-keyczar python-paramiko python-yaml git
    PIP_INSTALL=1
}

init_deb_new() {
    echo "deb http://ppa.launchpad.net/ansible/ansible/ubuntu trusty main" > /etc/apt/sources.list.d/ansible.list
    DEBIAN_FRONTEND=noninteractive apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 93C4A3FD7BB9C367
    DEBIAN_FRONTEND=noninteractive apt-get update -y
}

init_pip() {
    pip install MySQL-python Jinja2 httplib2 keyczar paramiko pyyaml
}

install() {
    if [ -z ${PIP_INSTALL} ]; then
        install_package
    else
        install_pip
    fi
}

install_package() {
    case ${DISTRO_NAME} in
        "debian" | "ubuntu" )
            DEBIAN_FRONTEND=noninteractive apt-get install -y ansible
            ;;
        "centos" | "scientific" | "redhat" )
            yum install -y ansible
            ;;
        "arch" )
            pacman -S --noconfirm ansible
            ;;
        "gentoo" )
            emerge -av app-admin/ansible
            ;;
        * )
            echo "Error: install not supported for this os"
    esac
}

install_pip() {
    pip install pysphere boto passlib dnspython
    pip install ansible
}

info
init
install