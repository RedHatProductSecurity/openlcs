# This library is copied from Corgi with some minor updates
# https://github.com/RedHatProductSecurity/component-registry/blob/main/corgi/tasks/sca.py
import re
import requests
import subprocess
from celery.utils.log import get_task_logger
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse


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

    response = requests.get(download_url, timeout=600)
    if response.status_code == 404:
        # Source URLs from Brew / _clone_source / _download_lookaside_sources
        # sometimes have .git in their path, and this ends up in package_name
        # Sometimes "name.git" fails but just "name" without ".git" will work
        # e.g. both kernel-rt.git or kmod-kvdo.git work without .git suffixes
        # We need this logic, even though we sometimes strip .git above,
        # in case cloning with .git works but fetching source with .git fails
        logger.info(
            "Downloading sources from: %s without .git, to: %s",
            download_url, target_filepath
        )
        response = requests.get(
            download_url.replace(".git", "", 1), timeout=600)
    response.raise_for_status()
    with target_filepath.open("wb") as target_file:
        target_file.write(response.content)


def _clone_source(lookaside_url: str,
                  source_url: str,
                  build_id: int,
                  dest_dir: str) -> Tuple[Path, str, str]:
    # (scheme, netloc, path, parameters, query, fragment)
    url = urlparse(source_url)

    # Older builds have git, git+https, git+ssh, etc, newer builds have https
    if not url.scheme.startswith("git") and url.scheme != "https":
        raise ValueError(
            f"Build {build_id} had a source_url with a non-git, "
            f"non-HTTPS protocol: {source_url}"
        )

    # It's an internal hostname, so we have to get it a little indirectly
    dist_git_hostname = lookaside_url.replace("https://", "", 1)
    dist_git_hostname = lookaside_url.replace("/repo", "", 1)

    protocol = url.scheme
    if protocol.startswith("git+"):
        # Make git+https, git+ssh, etc. into just https, ssh, etc
        protocol = protocol[4:]
    elif protocol == "git" and url.netloc == dist_git_hostname:
        # dist-git now requires us to use https when cloning
        protocol = "https"
        # The source_url of Brew old builds with "git" protocol was updated
        # in Corgi, CORGI-772
    # Else protocol was already https
    # Other protocols will raise an error above

    path = url.path
    if (
        url.netloc == dist_git_hostname
        and protocol in ("http", "https")
        and not path.startswith("/git/")
    ):
        # dist-git HTTP / HTTPS URLs require paths like /git/containers/ubi8
        # But Brew sometimes has only /containers/ubi8, which will fail
        path = f"/git{path}"
    # Else we're not using dist-git, or git+ssh became just ssh, or path
    # already had "/git/"
    git_remote = f"{protocol}://{url.netloc}{path}"

    # Use the original path when checking length, ignore any /git/ we added
    path_parts = url.path.rsplit("/", 2)
    if len(path_parts) != 3:
        raise ValueError(f"Build {build_id} had a source_url with a too-short "
                         f"path: {source_url}")
    package_type = path_parts[1]
    package_name = path_parts[2]
    commit = url.fragment

    target_path = Path(dest_dir)
    logger.info("Fetching %s to %s", git_remote, target_path)

    try:
        subprocess.check_call(
            ["/usr/bin/git", "clone", git_remote, target_path]
        )
    except subprocess.CalledProcessError as e:
        # There's a special case for dist-git web URLs with .git in them
        # If we aren't using dist-git, it's not a web URL, or .git isn't
        # present, then fail
        if (
            url.netloc != dist_git_hostname
            or protocol not in ("http", "https")
            or ".git" not in url.path
        ):
            raise e

        # dist-git source URLs from Brew are sometimes incorrect, give 404
        # We don't always remove .git in case some URLs require this
        # Use the updated path with /git/ which is always needed for the clone
        path = path.replace(".git", "", 1)
        git_remote = f"{protocol}://{url.netloc}{path}"

        # Use the updated path so .git doesn't end up in package_name
        # We already know we have the right number of path_parts, based on
        # check above
        path_parts = path.rsplit("/", 2)
        package_type = path_parts[1]
        package_name = path_parts[2]

        logger.info("Fetching %s without .git to %s", git_remote, target_path)
        subprocess.check_call(
            ["/usr/bin/git", "clone", git_remote, target_path]
        )

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
        return

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
        lookaside_url, source_url, build_id, dest_dir)
    if not raw_source:
        logger.warning("No sources found in %s", source_url)
        return
    _download_lookaside_sources(
        lookaside_url, raw_source, build_id, package_type, package_name)
