[![CircleCI](https://circleci.com/gh/simonbray/build-singularity/tree/master.svg?style=svg)](https://circleci.com/gh/simonbray/build-singularity/tree/master)

# Singularity build bot

The purpose of this repo is to ensure that all Docker containers located at https://quay.io/organization/biocontainers
are replicated as Singularity containers at https://depot.galaxyproject.org/singularity. New containers are added regularly to the Biocontainers organization on Quay and we want to ensure they are also available via Singularity.

The created containers are available on a [CernVM File System](https://cernvm.cern.ch/portal/filesystem). This is a POSIX read-only file system in user space that uses outgoing HTTP connections only, thereby avoiding most of the firewall issues of other network file systems. 

Learn more about CVMFS and how you can get access to more than 25000 software containers in our CVMFS example setup: https://github.com/usegalaxy-eu/cvmfs-example
