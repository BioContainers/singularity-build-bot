#!/usr/bin/env python

# This script is used to create a list of old builds of a package-container.
# The singularity containers here are to a large degree based on Bioconda packages. Hence, we can have for a package with
# a specific version, let's call it `mehr-licht:1.2`, multiple containers. For example the `mehr-licht:1.2--r341_0` container.
# The intention of this script is to return containers with old builds to safe space. To be clear there is still a container
# with the same version `mehr-licht:1.2`, just build against a newer R/Python/... version.

import os
import sys
from collections import defaultdict

image_dict = defaultdict(list)
image_to_archive = list()

for image in os.listdir(sys.argv[1]):
    if '--' in image:
        image_name, image_build_string = image.rsplit('--', 1)
        if '_' in image_build_string:
            try:
                build_string, build_number = image_build_string.rsplit('_', 1)
                image_dict[image_name].append( (build_string, int(build_number)) )
            except:
                # some wired image names, needs to be investigated
                pass

for k, v in image_dict.items():
    if not v:
        continue
    # We want to have the latest build so we need to sort for the latest build-number.
    # However, we can have the same build-number multiple-times with a different build-string.
    # In this case we sort the build-string. This is a bit arbritrary, but should cover hopefully most cases. 
    v.sort(key=lambda x: (x[1], x[0]))
    # pop the latest element after sorting. The latest element should be the most recent build, all remaining
    # images stay in the list and can be archived.
    v.pop()
    for build_string, build_number in v:
        name = f'{k}--{build_string}_{build_number}'
        if os.path.exists(name):
            image_to_archive.append(name)
            print(name)
        else:
            sys.exit(f'image "{name}" does not exist')

#do something useful with "image_to_archive"

