[![Singularity builds](https://github.com/BioContainers/singularity-build-bot/actions/workflows/main.yml/badge.svg?branch=master)](https://github.com/BioContainers/singularity-build-bot/actions/workflows/main.yml?branch=master)

# Singularity build bot

The purpose of this repo is to ensure that all Docker containers located at https://quay.io/organization/biocontainers
are replicated as Singularity containers at https://depot.galaxyproject.org/singularity. New containers are added regularly to the Biocontainers
organization on Quay and we want to ensure they are also available via Singularity.

The created containers are available on a [CernVM File System](https://cernvm.cern.ch/portal/filesystem). This is a POSIX read-only file system in user
space that uses outgoing HTTP connections only, thereby avoiding most of the firewall issues of other network file systems. 

Learn more about CVMFS and how you can get access to more than 97000 software containers in our CVMFS example setup: https://github.com/usegalaxy-eu/cvmfs-example

## Broader context

[Bioconda](https://bioconda.github.io/) and [Conda-Forge](https://conda-forge.org/) are collaborative communities focused on creating and maintaining Conda recipes.
These recipes facilitate the installation and management of scientific software,
providing researchers and developers with streamlined workflows. Packages from both [Bioconda](https://bioconda.github.io/) and [Conda-Forge](https://conda-forge.org/)
are hosted on [anaconda.org](https://anaconda.org/), a central repository that ensures reliable distribution.

The process for managing these packages is highly automated. Both Bioconda and Conda-Forge build and upload pre-compiled packages directly to anaconda.org. Bioconda goes a step further by testing all packages in minimal containerized environments to verify their compatibility and reliability. These containerized versions of the packages are subsequently pushed to quay.io/biocontainers, creating a robust and accessible ecosystem of ready-to-use environments.

For every package and every version within Bioconda, a corresponding pre-built container is available. This approach ensures that users have access to specific versions of tools in isolated and consistent environments.
Additionally, the multi-package-containers repository builds containers that include multiple Conda packages in a single container, known as mulled containers.
The naming convention for these containers relies on hashed package names and versions, providing unique identifiers for each.
Docker containers are directly pushed to quay.io/biocontainers, while Singularity images are uploaded to depot.galaxyproject.org/singularity.

To ensure seamless synchronization between these platforms, the [singularity-build-bot](https://github.com/BioContainers/singularity-build-bot) repository monitors quay.io for updates and uploads the corresponding containers
to [depot.galaxyproject.org](https://depot.galaxyproject.org/singularity/).
This ensures that all containers available on quay.io are also accessible via [depot.galaxyproject.org/singularity](https://depot.galaxyproject.org/singularity/).

Singularity containers hosted on depot.galaxyproject.org are further mirrored and geographically distributed using the CernVM File System (CVMFS).
This infrastructure optimizes access to containers globally, providing end-users with a reliable and efficient way to consume these resources.
The CVMFS distribution model parallels the accessibility of [quay.io/biocontainers](https://quay.io/organization/biocontainers), ensuring that users can seamlessly integrate these resources into their workflows.


## Problems?

Is a container missing? Or have you encountered something unexpected? Please [create an issue](https://github.com/BioContainers/singularity-build-bot/issues/new).
