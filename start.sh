#!/bin/bash
root="$(pwd)"
build=/io
static=/static
srcdir=${root}/src
cache_left=${root}/cache
cache_right=/root/.cache

staging=staging
wheelhouse=wheelhouse
disthouse=disthouse

source "$(dirname ${BASH_SOURCE[0]})/etc/config.sh"
source "$(dirname ${BASH_SOURCE[0]})/etc/functions.sh"

export GREP_MODE='-G'
if [[ $(uname) == Linux ]]; then
    export GREP_MODE='-P'
elif [[ $(uname) == Darwin ]]; then
    export GREP_MODE='-E'
fi

for project in "${projects[@]}"
do
    url="${host}/${org}/${project}"
    dest="${srcdir}/${project}"

    if [[ ! -d ${dest} ]]; then
        msg "Retrieving source for: ${project}"
        git clone --recursive "${url}" "${dest}" &>/dev/null
        if [[ $? != 0 ]]; then
            msg2 "Failed to clone: ${url}"
            continue
        fi
    fi

    pushd "${dest}" &>/dev/null
        tags=$(git tag | grep ${GREP_MODE} ${tag_regex} | tail -n ${tag_limit})
        echo "Tags: ${tags}"

        for tag in $tags
        do
            git fetch --all &>/dev/null
            git reset --hard &>/dev/null
            git clean -ffxd &>/dev/null
            git checkout "${tag}" &>/dev/null

            msg "Initializing Docker image: ${docker_image}"
            docker run --rm -i -t \
                -v "${cache_left}:${cache_right}" \
                -v "${root}:${static}" \
                -v "${dest}:${build}" \
                "${docker_image}" ${static}/build-project.sh "${project}"
        done
    popd &>/dev/null
done

wheels_binary=$(find ${staging} -type f -name '*cp*-cp*m*.whl')
wheels_universal=$(find ${staging} -type f -name '*-any.whl')
dists=$(find ${staging} -type f -name '*.tar.gz')


mkdir -p ${wheelhouse}
mkdir -p ${disthouse}

if [[ $wheels_binary ]]; then
    msg2 "Exporting binary wheels..."
    for whl in $wheels_binary; do
        docker run --rm -i -t \
            -v "${root}:${static}" \
            "${docker_image}" \
            auditwheel repair \
                "${static}/${whl}" \
                -w ${static}/wheelhouse
        if [[ $? == 0 ]]; then
            rm -f "${whl}"
        fi
    done
fi

set +e

# "auditwheel" wastes time for univeral wheels
if [[ $wheels_universal ]]; then
    msg2 "Exporting universal wheels..."
    for whl in $wheels_universal; do
        msg3 "$(basename ${whl})"
        mv "${whl}" "${wheelhouse}"
    done
fi

if [[ $dists ]]; then
    msg2 "Exporting source dists..."
    for dist in ${dists}; do
        msg3 "$(basename "${dist}")"
        mv "${dist}" "${disthouse}"
    done
fi
