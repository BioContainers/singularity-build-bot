#!/usr/bin/env python


"""Provide a command line tool for building Singularity images from BioContainers."""


import argparse
import asyncio
import logging
from enum import Enum
from functools import partial
from html.parser import HTMLParser
from pathlib import Path
from string import Template
from typing import List, Tuple, Dict, Optional, Iterable

import aiometer
import httpx
import pydantic
import rich.progress as rprog
import tenacity
from rich.logging import RichHandler


logger = logging.getLogger()


class RepositoryKind(str, Enum):
    """Define known kinds of repositories."""

    image = "image"


class RepositoryState(str, Enum):
    """Define known states of a repository."""

    NORMAL = "NORMAL"


class Repository(pydantic.BaseModel):
    """Define the repository data of interest."""

    namespace: str
    name: str
    is_public: bool
    kind: RepositoryKind
    state: RepositoryState


class RepositoryListResponse(pydantic.BaseModel):
    """Define the repository list data of interest."""

    repositories: List[Repository]
    next_page: Optional[str] = None


class RepositoryTag(pydantic.BaseModel):
    """Define the repository tag data of interest."""

    name: str


class SingleRepositoryResponse(Repository):
    """Define the single repository data of interest."""

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
        """Parse container images from a given tag and its attributes."""
        if tag != "a":
            return
        for attr, value in attrs:
            if attr != "href":
                continue
            if "%3A" in value:
                self._images.append(value.replace("%3A", ":", 1))


class QuayImageFetcher:
    @classmethod
    async def fetch_all(
        cls,
        api_url: str,
        repository: str = "biocontainers",
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        log_file: Path = Path(".quay.log"),
    ) -> List[str]:
        """Fetch all container images and their tags."""
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
        log_images(log_file=log_file, images=images)
        return images

    @classmethod
    async def _fetch_names(
        cls, client: httpx.AsyncClient, params: Dict[str, str]
    ) -> List[str]:
        """Fetch one or more batches of container images."""
        names = []
        with cls._progress_spinner() as pbar:
            task = pbar.add_task(description="Image Batch")
            repos = await cls._fetch_repository_list(client=client, params=params)
            names.extend((repo.name for repo in repos.repositories))
            pbar.update(task, advance=1)
            while repos.next_page:
                repos = await cls._fetch_repository_list(
                    client=client, params={**params, "next_page": repos.next_page}
                )
                names.extend((repo.name for repo in repos.repositories))
                pbar.update(task, advance=1)
        return names

    @classmethod
    def _progress_spinner(cls) -> rprog.Progress:
        """Create a rich progress spinner."""
        return rprog.Progress(
            rprog.TextColumn("[bold blue]{task.description}", justify="right"),
            rprog.SpinnerColumn(),
            "{task.completed:,}/?",
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
    async def _fetch_repository_list(
        client: httpx.AsyncClient, params: Dict[str, str]
    ) -> RepositoryListResponse:
        """Fetch a list of repositories and parse the response."""
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
        """
        Fetch the image tags for each given container image.

        Fetching is performed concurrently, in a resilient manner, observing the given
        limits.

        """
        requests = [
            client.build_request(method="GET", url=f"repository/{repository}/{name}")
            for name in names
        ]
        images = []
        with cls._progress_bar() as pbar:
            task = pbar.add_task(description="Image Tags", total=len(requests))
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
        """Fetch a single repository resource and parse the response."""
        response = await client.send(request=request)
        response.raise_for_status()
        return SingleRepositoryResponse.parse_obj(response.json())


class SingularityImageFetcher:
    @classmethod
    def fetch_all(
        cls,
        urls: Iterable[str],
        headers: Optional[Dict[str, str]] = None,
        log_file: Path = Path(".singularity.log"),
    ) -> List[str]:
        """Parse container images from each given URL."""
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
        with log_file.open("w") as handle:
            for img in images:
                handle.write(f"{img}\n")
        log_images(log_file=log_file, images=images)
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
        """Make a single GET request and return the response body as text."""
        response = client.get(url=url)
        response.raise_for_status()
        return response.text


def log_images(log_file: Path, images: List[str]) -> None:
    with log_file.open("w") as handle:
        for img in images:
            handle.write(f"{img}\n")


def get_new_images(
    quay_images: Iterable[str],
    singularity_images: Iterable[str],
    denylist: Iterable[str],
    log_file: Path = Path(".diff.log"),
) -> List[str]:
    """Identify new images from the given lists."""
    denylist = tuple(denylist)
    diff = sorted(frozenset(quay_images) - frozenset(singularity_images))
    log_images(log_file=log_file, images=diff)
    # Filter new images using the deny list.
    result = sorted(
        filter(
            lambda image: not any(image.startswith(entry) for entry in denylist),
            diff,
        )
    )
    others = []
    bioconductor = []
    for img in result:
        if img.startswith("bioconductor"):
            bioconductor.append(img)
        else:
            others.append(img)
    return others + bioconductor


def parse_denylist(filename: Path) -> List[str]:
    """Parse the list of images to skip."""
    with filename.open() as handle:
        return [entry for line in handle.readlines() if (entry := line.strip())]


def generate_build_script(filename: Path, images: List[str], template: Path) -> None:
    """Generate a build script from provided templates."""
    with template.open() as handle:
        img_template = Template(handle.read())
    with filename.open("a") as handle:
        for idx, img in enumerate(images, start=1):
            handle.write(img_template.substitute(img=img, idx=idx, total=len(images)))


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
    default_image_template = Path("image_template.sh")
    parser.add_argument(
        "--image-template",
        metavar="PATH",
        default=default_image_template,
        type=Path,
        help=f"The template for building a single Singularity image (default "
        f"'{default_image_template}'). Uses Python `string.Template` syntax.",
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
    default_singularity_urls = "https://depot.galaxyproject.org/singularity/"
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
    """Manage arguments and script execution."""
    args = parse_args(argv=argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True, rich_tracebacks=True)],
    )
    assert args.denylist.is_file(), f"File not found '{args.denylist}'."
    assert args.build_script.is_file(), f"File not found '{args.build_script}'."
    assert args.image_template.is_file(), f"File not found '{args.image_template}'."
    args.build_script.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Fetching quay.io BioContainers images.")
    quay_images = asyncio.run(QuayImageFetcher.fetch_all(api_url=args.quay_api))
    logger.info(f"Found {len(quay_images):,} images with tags.")
    logger.info("Fetching Singularity BioContainers images.")
    singularity_images = SingularityImageFetcher.fetch_all(
        urls=args.singularity.split(",")
    )
    logger.info(f"Found {len(singularity_images):,} images with tags.")
    logger.info("Parsing container image deny list.")
    denylist = parse_denylist(args.denylist)
    images = get_new_images(quay_images, singularity_images, denylist)
    if not images:
        logger.warning("No new images found.")
        return
    logger.info(f"{len(images):,} new images found. Generating build script.")
    generate_build_script(args.build_script, images, args.image_template)


if __name__ == "__main__":
    main()
