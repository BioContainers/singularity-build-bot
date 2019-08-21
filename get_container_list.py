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

def get_singularity_containers():
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
                    if attr[0] == 'href' and attr[1] != '../':
                        self.containers.append(attr[1].replace('%3A', ':'))
            except IndexError:
                pass

    parser = GetContainerNames()
    index = requests.get("https://depot.galaxyproject.org/singularity/")
    parser.feed(index.text)
    return parser.containers

def get_missing_containers(quay_list, singularity_list, blacklist_file=None):
    r"""
    Return list of quay containers that do not exist as singularity containers. Files stored in a blacklist will be ignored
    """
    blacklist = []
    if blacklist_file:
        blacklist = open(blacklist_file).read().split('\n')
    return [n for n in quay_list if n not in singularity_list and n not in blacklist]

############
### MAIN ###
############

u = get_quay_containers()
print(u)

lst = get_missing_containers(u, get_singularity_containers(), 'built_containers/blacklist.txt')

with open('build.sh', 'w') as f:
    for container in lst:
        f.write('singularity build built_containers/{} docker://quay.io/biocontainers/{}\n'.format(container, container))