#!/bin/bash

# Global config
project="$1"
root=/static
logdir="${root}/logs"
sysconfdir="${root}/etc"
staging="${root}/staging"
wheelhouse="${root}/wheelhouse"
path_orig="${PATH}"

# Build config
source "${sysconfdir}/config.sh"
source "${sysconfdir}/functions.sh"

if [[ -z $project ]]; then
    exit 255
fi

# Configure user to talk to artifactory (two-way)
pushd "${HOME}" &>/dev/null
    msg2 "Configuring pip and setuptools..."
    mkdir -p $HOME/.pip
    [[ -f ${sysconfdir}/pip.conf ]] && cp -a ${sysconfdir}/pip.conf ${HOME}/.pip
    [[ -f ${sysconfdir}/pypirc ]] && cp -a ${sysconfdir}/pypirc .pypirc
popd &>/dev/null

# Enter build directory
msg2 "Entering build directory"
cd /io

mkdir -p ${staging}/${project}

# Install forced dependencies
# Our packages are tend to be very inconsistent
for build_env in "${envs[@]}"; do
    PYBIN=/opt/python/${build_env}/bin
    export PATH="${PYBIN}:${path_orig}"
    hash -r
    pip install -q -r ${sysconfdir}/dev-requirements.txt 1>/dev/null
done

# Iterate through Python environments
msg2 "Building packages"
for build_env in "${envs[@]}"; do
    PYBIN=/opt/python/${build_env}/bin
    export PATH="${PYBIN}:${path_orig}"
    hash -r

    python_version=$(python -V 2>&1 | awk '{ print $2 }')
    project_version=$(git describe --long --tags 2>/dev/null || msg Unknown)
    BYTE_COMPILE=$(find . -type f -iname '*.c' -o -iname '*.f')

    # Setup logging
    logroot=${logdir}/${python_version}/${project}/${project_version}
    mkdir -p "${logroot}"

    for dist in bdist_wheel sdist; do
        msg3 "[${python_version}][${dist}][${project}-${project_version}]"

        python setup.py ${dist} -d ${staging}/${project} \
            1>${logroot}/${dist}.stdout \
            2>${logroot}/${dist}.stderr

        if [[ $? != 0 ]] && [[ ${dist} == bdist_wheel ]]; then
            # Ahhhhhhhrrrrrrrgggg
            pip wheel -w ${staging}/${project} ${dist} \
            1>${logroot}/${dist}.stdout \
            2>${logroot}/${dist}.stderr
        fi

        # On failure, write log to console
        if [[ $? != 0 ]]; then
            cat ${logroot}/${dist}.stderr
        fi
    done

    # When not compiling Python extensions don't continue on
    # to the next interpreter version
    if [[ ! ${BYTE_COMPILE} ]]; then
        break
    fi
done

echo
