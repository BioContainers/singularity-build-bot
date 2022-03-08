#!/usr/bin/env python
import argparse
import asyncio
import logging
from enum import Enum
from functools import partial
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Iterable

import aiometer
import httpx
import pydantic
import rich.progress as rprog
import tenacity
from rich.logging import RichHandler


logger = logging.getLogger()


class RepositoryKind(str, Enum):

    image = "image"


class RepositoryState(str, Enum):

    NORMAL = "NORMAL"


class Repository(pydantic.BaseModel):

    namespace: str
    name: str
    is_public: bool
    kind: RepositoryKind
    state: RepositoryState


class RepositoryListResponse(pydantic.BaseModel):

    repositories: List[Repository]
    next_page: Optional[str] = None


class RepositoryTag(pydantic.BaseModel):

    name: str


class SingleRepositoryResponse(Repository):

    tags: Dict[str, RepositoryTag]


class ContainerImageParser(HTMLParser):
    """Define a parser for container names and tags."""

    def __init__(self, **kwargs) -> None:
        """Initialize a default container parser."""
        super().__init__(**kwargs)
        self._images = []

    @property
    def images(self) -> List[str]:
        """Return the list of parsed container images."""
        return self._images.copy()

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag != "a":
            return
        for attr, value in attrs:
            if attr != "href":
                continue
            if ":" in value:
                self._images.append(value)


class QuayImageFetcher:
    @classmethod
    async def fetch_all(
        cls,
        api_url: str,
        repository: str = "biocontainers",
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        if headers is None:
            headers = {
                "Accept-Encoding": "gzip",
                "Accept": "application/json",
                "User-Agent": "singularity-build-bot",
            }
        if params is None:
            params = {"public": "true", "repo_kind": "image"}
        params["namespace"] = repository
        async with httpx.AsyncClient(
            base_url=api_url, headers=headers, timeout=httpx.Timeout(12)
        ) as client:
            names = await cls._fetch_names(client=client, params=params)
            images = await cls._fetch_tags(
                client=client, repository=repository, names=names
            )
        return images

    @classmethod
    async def _fetch_names(
        cls, client: httpx.AsyncClient, params: Dict[str, str]
    ) -> List[str]:
        names = []
        logger.debug("Fetching batch 1/?")
        repos = await cls._fetch_repository_list(client=client, params=params)
        names.extend((repo.name for repo in repos.repositories))
        counter = 2
        while repos.next_page:
            logger.debug("Fetching batch %d/?", counter)
            repos = await cls._fetch_repository_list(
                client=client, params={**params, "next_page": repos.next_page}
            )
            names.extend((repo.name for repo in repos.repositories))
            counter += 1
        return names

    @staticmethod
    @tenacity.retry(
        wait=tenacity.wait_random_exponential(),
        stop=tenacity.stop_after_attempt(5),
        reraise=True,
        retry=tenacity.retry_if_exception_type(httpx.HTTPError),
        before=tenacity.before_log(logger, logging.DEBUG),
    )
    async def _fetch_repository_list(
        client: httpx.AsyncClient, params: Dict[str, str]
    ) -> RepositoryListResponse:
        response = await client.get("repository", params=params)
        response.raise_for_status()
        return RepositoryListResponse.parse_obj(response.json())

    @classmethod
    async def _fetch_tags(
        cls,
        client: httpx.AsyncClient,
        repository: str,
        names: List[str],
        max_concurrency: int = 10,
        max_per_second: int = 10,
    ) -> List[str]:
        requests = [
            client.build_request(method="GET", url=f"repository/{repository}/{name}")
            for name in names
        ]
        images = []
        with cls._progress_bar() as pbar:
            task = pbar.add_task(description="Repository Tags", total=len(requests))
            async with aiometer.amap(
                partial(cls._fetch_single_repository, client),
                requests,
                max_at_once=max_concurrency,
                max_per_second=max_per_second,
            ) as results:
                async for repo in results:  # type: SingleRepositoryResponse
                    images.extend((f"{repo.name}:{tag}" for tag in repo.tags))
                    pbar.update(task, advance=1)
        return images

    @classmethod
    def _progress_bar(cls) -> rprog.Progress:
        """Create a rich progress bar."""
        return rprog.Progress(
            rprog.TextColumn("[bold blue]{task.description}", justify="right"),
            rprog.BarColumn(bar_width=None),
            "[progress.percentage]{task.completed:,}/{task.total:,}({task.percentage:>3.1f}%)",
            " ",
            rprog.TimeRemainingColumn(),
            " ",
            rprog.TimeElapsedColumn(),
        )

    @staticmethod
    @tenacity.retry(
        wait=tenacity.wait_random_exponential(),
        stop=tenacity.stop_after_attempt(5),
        reraise=True,
        retry=tenacity.retry_if_exception_type(httpx.HTTPError),
        before=tenacity.before_log(logger, logging.DEBUG),
    )
    async def _fetch_single_repository(
        client: httpx.AsyncClient, request: httpx.Request
    ) -> SingleRepositoryResponse:
        response = await client.send(request=request)
        response.raise_for_status()
        return SingleRepositoryResponse.parse_obj(response.json())


class SingularityImageFetcher:
    @classmethod
    def fetch_all(
        cls,
        urls: Iterable[str],
        headers: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        if headers is None:
            headers = {
                "Accept-Encoding": "gzip",
                "Accept": "text/html",
                "User-Agent": "singularity-build-bot",
            }
        images = []
        with httpx.Client(headers=headers) as client:
            for url in urls:
                parser = ContainerImageParser()
                if response := cls._fetch_images(client=client, url=url):
                    parser.feed(response)
                    images.extend(parser.images)
                else:
                    logger.warning("No images found at '%s'.", url)
        return images

    @staticmethod
    @tenacity.retry(
        wait=tenacity.wait_random_exponential(),
        stop=tenacity.stop_after_attempt(5),
        reraise=True,
        retry=tenacity.retry_if_exception_type(httpx.HTTPError),
        before=tenacity.before_log(logger, logging.DEBUG),
    )
    def _fetch_images(client: httpx.Client, url: str) -> Optional[str]:
        response = client.get(url=url)
        if response.status_code == 404:
            return
        response.raise_for_status()
        return response.text


def get_new_images(
    quay_images: Iterable[str],
    singularity_images: Iterable[str],
    denylist: Iterable[str],
) -> List[str]:
    denylist = tuple(denylist)
    result = frozenset(quay_images) - frozenset(singularity_images)
    # Filter new images using the deny list.
    # FIXME: Is it necessary to sort bioconductor images to the end as before?
    return sorted(
        filter(
            lambda image: not any(image.startswith(entry) for entry in denylist),
            result,
        )
    )


def parse_denylist(filename: Path) -> List[str]:
    with filename.open() as handle:
        return [entry for line in handle.readlines() if (entry := line.strip())]


def generate_build_script(filename: Path, images: List[str]) -> None:
    with filename.open("w") as handle:
        for idx, name in enumerate(images, start=1):
            handle.write(
                f"sudo singularity build {name} docker://quay.io/biocontainers/{name} > /dev/null 2>&1 && rsync -azq -e 'ssh -i ssh_key -o StrictHostKeyChecking=no' ./{name} singularity@depot.galaxyproject.org:/srv/nginx/depot.galaxyproject.org/root/singularity/ && rm {name} && echo 'Container {name} built ({idx}/{len(images)}).'\n"
            )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Define and immediately parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Find new BioContainers images for which no Singularity image "
        "exists yet and generate a build script for them.",
    )
    default_denylist = Path("skip.list")
    parser.add_argument(
        "--denylist",
        metavar="PATH",
        default=default_denylist,
        type=Path,
        help=f"File containing image names to skip; one per line (default "
        f"'{default_denylist}').",
    )
    default_build_script = Path("build.sh")
    parser.add_argument(
        "--build-script",
        metavar="PATH",
        default=default_build_script,
        type=Path,
        help=f"Output the Singularity build script (default '{default_build_script}').",
    )
    default_quay_api = "https://quay.io/api/v1/"
    parser.add_argument(
        "--quay-api",
        metavar="URL",
        type=str,
        default=default_quay_api,
        help=f"The base URL for the quay.io API; must end with a '/' (default "
        f"'{default_quay_api}').",
    )
    default_singularity_urls = ",".join(
        [
            "https://depot.galaxyproject.org/singularity/new/",
            "https://depot.galaxyproject.org/singularity/",
        ]
    )
    parser.add_argument(
        "--singularity",
        metavar="URL[,URL]",
        type=str,
        default=default_singularity_urls,
        help=f"One or more URLs for Singularity depots; must end with a '/' and be "
        f"separated by commas (default '{default_singularity_urls}').",
    )
    default_log_level = "INFO"
    parser.add_argument(
        "-l",
        "--log-level",
        help=f"The desired log level (default {default_log_level}).",
        choices=("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
        default=default_log_level,
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv=argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True, rich_tracebacks=True)],
    )
    assert args.denylist.is_file(), f"File not found '{args.denylist}'."
    args.build_script.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Fetching quay.io BioContainers images.")
    quay_images = asyncio.run(QuayImageFetcher.fetch_all(api_url=args.quay_api))
    logger.info("Fetching Singularity BioContainers images.")
    singularity_images = SingularityImageFetcher.fetch_all(
        urls=args.singularity.split(",")
    )
    logger.info("Parsing container image deny list.")
    denylist = parse_denylist(args.denylist)
    images = get_new_images(quay_images, singularity_images, denylist)
    if not images:
        logger.warning("No new images found.")
        return
    logger.info("%d new images found. Generating build script.", len(images))
    generate_build_script(args.build_script, images)


if __name__ == "__main__":
    main()
