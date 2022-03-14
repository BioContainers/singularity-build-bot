#!/usr/bin/env bash

set -u

build_singularity_image() {
    local image=${1}
    local index=${2}
    local total=${3}
    local source=${4:-'docker://quay.io/biocontainers'}
    local destination=${5:-'singularity@depot.galaxyproject.org:/srv/nginx/depot.galaxyproject.org/root/singularity/'}

    singularity build "${image}" "${source}/${image}" > /dev/null 2>&1
    rsync -azq -e 'ssh -i ssh_key -o StrictHostKeyChecking=no' "./${image}" "${destination}"
    rm "./${image}"
    singularity cache clean --type blob --force
    echo "Container ${image} built (${index}/${total})."
}
