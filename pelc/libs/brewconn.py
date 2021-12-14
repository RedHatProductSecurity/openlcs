# -*- coding: utf-8 -*-

import datetime
import koji
import os
import re
import shutil
import subprocess
import tempfile
from kobo.shortcuts import run
from urllib.parse import urlparse


class BrewConnector:
    """
    Object used for communication with Brew or Koji
    """

    def __init__(self, config, cache_timeout=datetime.timedelta(hours=1)):
        self.config = config
        self.download_url = self.config.get('BREW_DOWNLOAD')
        self.web_url = self.config.get('BREW_WEBURL')
        self.web_service = self.config.get('BREW_WEBSERVICE')

        self._service = koji.ClientSession(self.web_service)
        self._timeout = cache_timeout
        self._cache_build = {}

    def download_build_source(self, build_id, dest_dir):
        """
        Download srpm/source archive for build to destination.
        """
        source = self.get_build_source(build_id)
        if source.get('scm') == 'git':
            tmp_clone = tempfile.mkdtemp(prefix='pelc-clone-', dir='/var/tmp')
            try:
                # Full clone is needed to match koji's behavior.
                # git archive --remote won't work, as it doesn't accept
                # commit SHAs
                try:
                    subprocess.check_call(
                        ['git', 'clone', '-n', source['url'], tmp_clone]
                    )
                except subprocess.CalledProcessError:
                    raise RuntimeError(
                        "Cloning git repository failed"
                    ) from None
                git_src_file = os.path.join(dest_dir, 'git-src.tar')
                with open(git_src_file, 'w', encoding='utf8') as out:
                    module = source.get('module')
                    module_arg = [module] if module else []
                    try:
                        subprocess.check_call(
                            ['git', 'archive', source['rev']] + module_arg,
                            stdout=out, cwd=tmp_clone,
                        )
                    except subprocess.CalledProcessError:
                        raise RuntimeError(
                            "Failed to create source archive from git"
                        ) from None
            finally:
                shutil.rmtree(tmp_clone, ignore_errors=True)
            return 0, ''

        if 'src' not in source:
            return

        file_path = self._get_pathinfo(build_id, source)
        url = self._format_url(file_path)
        rc, output = run(f'wget {url}', can_fail=True, workdir=dest_dir)
        return rc, output

    def _format_url(self, pathinfo):
        """
        Formats URL for file download.
        """
        pathinfo = re.sub(koji.pathinfo.topdir, '', pathinfo)
        return f'{self.download_url}/{pathinfo}'

    def _get_pathinfo(self, build_id, source):
        """
        Get pathinfo for build source.
        """
        pathinfo = koji.pathinfo
        build = self._get_cached_build(build_id)

        if source['type'] == 'rpm':
            file_name = pathinfo.rpm(source['src'])
            file_path = pathinfo.build(build) + '/' + file_name
        elif source['type'] == 'maven':
            file_name = pathinfo.mavenfile(source['src'])
            file_path = pathinfo.mavenbuild(build) + '/' + file_name
        elif source['type'] == 'win':
            file_name = pathinfo.winfile(source['src'])
            file_path = pathinfo.winbuild(build) + '/' + file_name
        else:
            file_path = pathinfo.imagebuild(build) + '/' + source['src']
        return file_path

    def _get_cached(self, cache, key, call):
        """
        Get cached value, update cache when non-existent or expired.
        """
        cache = getattr(self, cache)
        cval = cache.get(key)
        if cval and cval['expires'] > datetime.datetime.today():
            result = cval['result']
        else:
            expire_date = datetime.datetime.today() + self._timeout
            call = getattr(self._service, call)
            result = call(key)
            cache[key] = {'expires': expire_date, 'result': result}
        return result

    def _get_cached_build(self, build_id):
        return self._get_cached('_cache_build', build_id, 'getBuild')

    def get_build_source(self, build_id):
        """
        Return srpm/source archive for build.
        """
        source = {}
        build = self._get_cached_build(build_id)
        srpms = self._service.listRPMs(build_id, arches='src')
        if srpms:
            source.update({'src': srpms[0], 'type': 'rpm'})
        else:
            # Only deal with source archives in type: tar, zip, jar
            archive_types = ['tar', 'zip', 'jar']
            for _type in ('maven', 'win', 'image'):
                archives = self._service.listArchives(build_id, type=_type)
                if archives:
                    source.update({'type': _type})
                    for a in archives:
                        if a['type_name'] in archive_types and re.search(
                                r"sources\.(tar|zip|jar)", a['filename']):
                            # Get source file: sources-->scm-sources
                            source.update({'src': a})
                            if not re.search("scm-sources", a['filename']):
                                break
                    break
            if 'src' not in source and build.get('source'):
                source_url = urlparse(build['source'])
                scheme_match = re.match(r'^git(?:\+(.*))?', source_url.scheme)
                if scheme_match:
                    scheme = scheme_match.group(1) or 'git'
                    url = '{}://{}{}'.format(
                        scheme, source_url.netloc, source_url.path,
                    )
                    revision = source_url.fragment
                    # Check that it is not a branch
                    try:
                        git_out = subprocess.check_output(
                            ['git', 'ls-remote', '-q', url, revision]
                        )
                    except subprocess.CalledProcessError:
                        raise RuntimeError(
                            "Failed to contact the git remote at {}"
                            .format(url)
                        ) from None
                    if git_out and 'refs/tags/' not in git_out:
                        raise RuntimeError(
                            "Import with SCM URL only allowed from a commit or"
                            " a tag. Please, make an adhoc import from a"
                            " tarball instead"
                        )
                    source['scm'] = 'git'
                    source['url'] = url
                    source['rev'] = revision
                    source['module'] = source_url.query
        return source

    def get_build(self, build_info):
        """
        Return information about a build.

        build_info may be either a int ID, a string NVR, or a map containing
        'name', 'version' and 'release.
        """
        return self._service.getBuild(build_info)
