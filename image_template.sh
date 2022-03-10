
singularity build ${img} "$${SOURCE}/${img}" > /dev/null 2>&1 \
    && rsync -azq -e 'ssh -i ssh_key -o StrictHostKeyChecking=no' ./${img} "$${DESTINATION}" \
    && rm ${img} \
    && singularity cache clean --type blob --force \
    && echo 'Container ${img} built (${idx}/${total}).'
