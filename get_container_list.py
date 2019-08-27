import re
import requests

try:
    from html.parser import HTMLParser
except ImportError:  # python 2
    from HTMLParser import HTMLParser

QUAY_API_ENDPOINT = 'https://quay.io/api/v1/repository'

def get_quay_containers(repository='biocontainers'):
    """
    Get all quay containers in the biocontainers repo
    """
    containers = []

    repos_parameters = {'public': 'true', 'namespace': repository}
    repos_headers = {'Accept-encoding': 'gzip', 'Accept': 'application/json'}
    repos_response = requests.get(
        QUAY_API_ENDPOINT, headers=repos_headers, params=repos_parameters, timeout=12)

    repos = repos_response.json()['repositories']

    for repo in repos:
        # logging.info(repo)
        tags_response = requests.get(
            "%s/%s/%s" % (QUAY_API_ENDPOINT, repository, repo['name']))
        tags = tags_response.json()['tags']
        for tag in tags:
            containers.append('%s:%s' % (repo['name'], tag))

    return containers

def get_singularity_containers(url="https://depot.galaxyproject.org/singularity/new/"):
    """
    Get all existing singularity containers from "https://depot.galaxyproject.org/singularity/"
    """
    class GetContainerNames(HTMLParser):  # small parser which gets list of containers
        def __init__(self):
            HTMLParser.__init__(self)
            self.containers = []

        def handle_starttag(self, tag, attrs):
            try:
                for attr in attrs:
                    if attr[0] == 'href' and re.match('.*%3A.*', attr[1]):
                        self.containers.append(attr[1].replace('%3A', ':'))
            except IndexError:
                pass

    parser = GetContainerNames()
    index = requests.get(url)
    parser.feed(index.text)
    return parser.containers

def check_multiple_singularity_directories(urls):
    """
    For a list of urls, get Singularity containers for each and find the union
    """
    containers = []
    for url in urls:
        containers += get_singularity_containers(url)
    return set(containers)

def get_missing_containers(quay_list, singularity_list, blacklist_file=None):
    r"""
    Return list of quay containers that do not exist as singularity containers. Files stored in a blacklist will be ignored
    """
    blacklist = []
    if blacklist_file:
        blacklist = open(blacklist_file).read().splitlines()
    rgx = "(" + ")|(".join(blacklist) + ")"
    return [n for n in quay_list if n not in singularity_list and not re.match(rgx, n)]

############
### MAIN ###
############

SINGULARITY_DIRECTORIES = ["https://depot.galaxyproject.org/singularity/new/", "https://depot.galaxyproject.org/singularity/bot/"] # dirs to check for containers

print('Getting list of containers to build. This may take a while...')
quay = get_quay_containers()
sing = check_multiple_singularity_directories(SINGULARITY_DIRECTORIES)

lst = get_missing_containers(quay, sing, 'skip.list')

with open('build.sh', 'w') as f:
    c_no = 0
    for container in lst:
        f.write("sudo singularity build {0} docker://quay.io/biocontainers/{0} 1> /dev/null && scp -q ./{0} singularity@orval.galaxyproject.org:/srv/nginx/depot.galaxyproject.org/root/singularity/bot/ && rm {0} && echo 'Container {1} ({0}) of {2} built.'\n".format(container, c_no, len(lst)))

print('{} containers found. Building...'.format(len(lst)))
