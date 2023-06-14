# This library is copied from Corgi with some minor updates
# https://github.com/RedHatProductSecurity/component-registry/blob/main/corgi/tasks/sca.py
import re
import subprocess
from celery.utils.log import get_task_logger
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

import requests
from requests import Response


LOOKASIDE_SCRATCH_SUBDIR = "lookaside"
LOOKASIDE_REGEX_SOURCE_PATTERNS = [
    # https://regex101.com/r/xYoHtX/1
    r"^(?P<hash>[a-f0-9]*)[ ]+(?P<file>[a-zA-Z0-9.\-_]*)",
    # https://regex101.com/r/mjtKif/1
    r"^(?P<alg>[A-Z0-9]*) \((?P<file>[a-zA-Z0-9.-]*)\) = (?P<hash>[a-f0-9]*)",
]
lookaside_source_regexes = tuple(
        re.compile(p) for p in LOOKASIDE_REGEX_SOURCE_PATTERNS
)
logger = get_task_logger(__name__)


def _download_source(download_url: str, target_filepath: Path) -> None:
    package_dir = Path(target_filepath.parents[0])
    # This can be called multiple times for each source in the lookaside cache.
    # We allow existing package_dir not to fail in case this is a subsequent
    # file we are downloading
    package_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading sources from: %s, to: %s",
                download_url, target_filepath)
    r: Response = requests.get(download_url, timeout=600)
    r.raise_for_status()
    with target_filepath.open("wb") as target_file:
        target_file.write(r.content)


def _clone_source(source_url: str,
                  build_id: int,
                  dest_dir: str) -> Tuple[Path, str, str]:
    # (scheme, netloc, path, parameters, query, fragment)
    url = urlparse(source_url)

    # We only support git, git+https, git+ssh
    if not url.scheme.startswith("git"):
        raise ValueError(
            f"Build {build_id} had a source_url with a non-git protocol: "
            f"{source_url}"
        )

    protocol = url.scheme
    if protocol.startswith("git+"):
        protocol = protocol.removeprefix("git+")
    git_remote = f"{protocol}://{url.netloc}{url.path}"
    path_parts = url.path.rsplit("/", 2)
    if len(path_parts) != 3:
        raise ValueError(f"Build {build_id} had a source_url with a too-short "
                         f"path: {source_url}")
    package_type = path_parts[1]
    package_name = path_parts[2]
    commit = url.fragment
    target_path = Path(dest_dir)
    logger.info("Fetching %s to %s", git_remote, target_path)
    subprocess.check_call(["/usr/bin/git", "clone", git_remote, target_path])
    subprocess.check_call(
        ["/usr/bin/git", "checkout", commit],
        cwd=target_path, stderr=subprocess.DEVNULL
    )
    return target_path, package_type, package_name


def _download_lookaside_sources(lookaside_url: str,
                                distgit_sources: Path,
                                build_id: int,
                                package_type: str,
                                package_name: str):
    lookaside_source = distgit_sources / "sources"
    if not lookaside_source.exists():
        logger.warning("No lookaside sources in %s", distgit_sources)
        return []

    with open(lookaside_source, "r", encoding='utf-8') as source_content_file:
        source_content = source_content_file.readlines()

    for line in source_content:
        match = None
        for regex in lookaside_source_regexes:
            match = regex.search(line)
            if match:
                break  # lookaside source regex loop
        if not match:
            continue  # source content loop
        lookaside_source_matches = match.groupdict()
        lookaside_source_filename = lookaside_source_matches.get("file", "")
        lookaside_source_checksum = lookaside_source_matches.get("hash", "")
        lookaside_hash_algorith = lookaside_source_matches.get(
            "alg", "md5").lower()
        lookaside_path_base: Path = Path(lookaside_source_filename)
        lookaside_path = Path.joinpath(
            lookaside_path_base,
            lookaside_hash_algorith,
            lookaside_source_checksum,
            lookaside_source_filename,
        )
        # https://<host>/repo/rpms/zsh/zsh-5.0.2.tar.bz2/md5/
        # b8f2ad691acf58b3252225746480dcad/zsh-5.0.2.tar.bz
        lookaside_download_url = (
            f"{lookaside_url}/{package_type}/{package_name}/{lookaside_path}"
        )
        # eg. /srv/git/repos/openlcs/tmp/download_ac2ray1u/zsh-5.0.2.tar.bz2
        target_filepath = distgit_sources / f"{lookaside_path_base}"
        _download_source(lookaside_download_url, target_filepath)


def get_distgit_sources(lookaside_url: str,
                        source_url: str,
                        build_id: int,
                        dest_dir: str):
    raw_source, package_type, package_name = _clone_source(
        source_url, build_id, dest_dir)
    if not raw_source:
        return []
    _download_lookaside_sources(
        lookaside_url, raw_source, build_id, package_type, package_name)
