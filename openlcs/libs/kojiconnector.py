# -*- coding: utf-8 -*-
import datetime
import ijson
import koji
import os
import re
import shutil
import subprocess
import tempfile
import uuid

from kobo.shortcuts import run
from urllib.parse import urlparse
from urllib.request import urlopen

from libs.common import get_component_flat, group_components


class KojiConnector:
    """
    Object used for communication with Brew or Koji
    """

    def __init__(self, config, cache_timeout=datetime.timedelta(hours=1)):
        self.config = config
        self.download_url = self.config.get('KOJI_DOWNLOAD')
        self.web_url = self.config.get('KOJI_WEBURL')
        self.web_service = self.config.get('KOJI_WEBSERVICE')

        self._service = koji.ClientSession(self.web_service)
        self._timeout = cache_timeout
        self._cache_build = {}

    def get_maven_build(self, build_info, strict=False):
        """
        Retrieve Maven-specific information about a build.
        buildInfo can be either a string (n-v-r) or an integer
        (build ID).
        Returns a map containing the following keys:

        build_id: id of the build (integer)
        group_id: Maven groupId (string)
        artifact_id: Maven artifact_Id (string)
        version: Maven version (string)
        """
        return self._service.getMavenBuild(build_info, strict)

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

    def get_pom_pathinfo(self, build_id):
        """
        Shortcut to get pom file pathinfo for maven builds.
        "get_build_source" is highly coupled thus I'd rather have a shortcut
        instead of reusing the exising get_build_source.
        """
        build = self._get_cached_build(build_id)
        if 'maven' not in self.get_build_type(build):
            raise ValueError("Not a maven build.") from None
        else:
            source = {}
            maven_build = self.get_maven_build(build_info=build_id)
            artifact_id = maven_build.get('artifact_id')
            version = maven_build.get('version')
            # all maven builds in brew/koji get one non-nullable 'xxx.pom'
            # file, where 'xxx' follows convention of 'artifactId-version'.
            # artifactId/version can be retrieved from `get_maven_build`.
            pom_filename = "-".join([artifact_id, version]) + ".pom"
            archives = self._service.listArchives(
                build_id, type='maven', filename=pom_filename)
            if archives:
                source.update({'src': archives[0]})
                source.update({'type': 'maven'})
                return self._get_pathinfo(build_id, source)
            # method valid only for maven builds
            else:
                err_msg = f"pom file {pom_filename} not found."
                raise ValueError(err_msg) from None

    def get_build_type(self, build_info):
        """
        Return build type based on build_info.
        """
        if build_info.get('build_type') == 'rpm':
            return 'rpm'
        else:
            return self._service.getBuildType(build_info)

    def get_build(self, build_info):
        """
        Return information about a build.

        build_info may be either an int ID, a string NVR, or a map containing
        'name', 'version' and 'release.
        """
        return self._service.getBuild(build_info)

    def get_build_from_nvra(self, rpm_nvra):
        """
        Return the build that corresponds to the rpm_nvra.
        """
        rpm_info = self._service.getRPM(rpm_nvra)
        if rpm_info is None:
            return None
        build_id = rpm_info.get('build_id')
        return self.get_build(build_id)

    def get_build_extended(self, package_nvr=None, rpm_nvra=None):
        """
        Extended version of `get_build`, serves as a shortcut to get build
        using various forms.
        """
        if package_nvr:
            build = self.get_build(package_nvr)
            params = package_nvr
        elif rpm_nvra:
            build = self.get_build_from_nvra(rpm_nvra)
            params = rpm_nvra
        else:
            err_msg = "Package NVR or NVRA is required."
            raise ValueError(err_msg)

        if not build:
            raise RuntimeError(f'No build found for {params} in Brew/Koji.')
        return build

    def get_osbs_build_kind(self, build):
        """
        Get the osbs build type from build extra.
        """
        extra = build.get('extra', None)
        osbs_build = extra.get('osbs_build') if extra else None
        return osbs_build.get('kind') if osbs_build else None

    def is_source_container_build(self, build):
        return self.get_osbs_build_kind(build) == "source_container_build"

    def get_binary_nvr(self, sc_nvr):
        """
        Accept source container nvr that the brew build info is
        extra.osbs_build.kind: source_container_build
        Return the mapping binary nvr for the source build
        """
        build = self.get_build(sc_nvr)
        container_kind = self.get_osbs_build_kind(build)
        try:
            if container_kind == 'source_container_build':
                return build['extra']['image']['sources_for_nvr']
        except KeyError as err:
            raise KeyError(f"Failed to get binary nvr: {err}") from None

    def list_builds(self, package_id, state, query_opts):
        """
        Return a list of builds for a package with the state and queryOpts.
        """
        return self._service.listBuilds(
                packageID=package_id, state=state,
                queryOpts=query_opts)

    def list_tagged(self, tag):
        """
        Return a list of builds with the tag.
        """
        return self._service.listTagged(tag)

    def get_package_id(self, package_name):
        """
        Return the package id for a package name.
        """
        return self._service.getPackageID(package_name)

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
                            f"Failed to contact the git remote at {url}"
                        ) from None
                    if git_out and 'refs/tags/' not in git_out:
                        raise RuntimeError(
                            "Import with SCM URL only allowed from a commit or"
                            " a tag. Please, make an adhoc import from a"
                            " tarball instead"
                        ) from None
                    source['scm'] = 'git'
                    source['url'] = url
                    source['rev'] = revision
                    source['module'] = source_url.query
        return source

    def download_build_source(self, build_id, dest_dir):
        """
        Download Brew/Koji build source to destination.
        """
        url = ""
        source = self.get_build_source(build_id)
        scm = source.get('scm')
        if scm and scm == 'git':
            tmp_clone = tempfile.mkdtemp(
                    prefix='openlcs_clone_', dir='/var/tmp')
            try:
                # Full clone is needed to match koji's behavior.
                # git archive --remote won't work, as it doesn't accept
                # commit SHAs
                try:
                    cmd = ['git', 'clone', '-n', source['url'], tmp_clone]
                    subprocess.check_call(cmd, shell=False)
                except subprocess.CalledProcessError as err:
                    err_msg = f'Failed to clone git repository. Reason: {err}'
                    raise RuntimeError(err_msg) from None
                git_src_file = os.path.join(dest_dir, 'git-src.tar')
                with open(git_src_file, 'w', encoding='utf8') as out:
                    module = source.get('module')
                    cmd = ['git', 'archive', source['rev']]
                    if module:
                        cmd.append(module)
                    try:
                        subprocess.check_call(cmd, shell=False, stdout=out,
                                              cwd=tmp_clone)
                    except subprocess.CalledProcessError as err:
                        err_msg = ('Failed to create source archive from '
                                   f'git: {err}')
                        raise RuntimeError(err_msg) from None
            finally:
                shutil.rmtree(tmp_clone, ignore_errors=True)
            return source.get('url')
        elif 'src' in source:
            source_path = self._get_pathinfo(build_id, source)
            url = self._format_url(source_path)
            cmd = ['wget', url, '-q', '--show-progress']
            try:
                subprocess.check_call(cmd, shell=False, cwd=dest_dir)
            except subprocess.CalledProcessError as err:
                err_msg = f'Failed to download build source. Reason: {err}'
                raise RuntimeError(err_msg) from None
            return url
        else:
            raise RuntimeError('Failed to find build source.') from None

    def download_pom(self, file_path, dest_dir):
        """
        Download xxx.pom file for maven build, to destination dir.
        """
        url = self._format_url(file_path)
        rc, output = run('wget %s' % url, can_fail=True, workdir=dest_dir)
        return rc, output

    def download_archive(self, build, type_path, archive, dest_dir):
        """
        Download build archive from Brew/Koji.
        """
        package_name = build.get('package_name')
        version = build.get('version')
        release = build.get('release')
        archive_name = archive.get('filename')

        archive_file_path = os.path.join(
            'packages', package_name, version,
            release, type_path, archive_name)
        image_url = self._format_url(archive_file_path)
        cmd = ['wget', image_url, '-q', '--show-progress']
        try:
            subprocess.check_call(cmd, cwd=dest_dir)
        except Exception as e:
            raise ValueError("Failed to download archive: %s " % e) from None

    def download_container_image_archives(self, build, dest_dir, arch=None):
        """
        Find the source image and Download from Brew/Koji.
        """
        build_id = build.get('build_id')
        all_archives = self._service.listArchives(build_id)
        if not all_archives:
            raise ValueError("No build archives found.") from None

        type_path = 'images'
        if arch:
            archive = [archive for archive in all_archives
                       if archive.get('btype') == 'image' and
                       arch in archive.get('filename')]
            if archive:
                self.download_archive(build, type_path, archive[0], dest_dir)
            else:
                err_msg = "No image found for arch %s." % arch
                raise ValueError(err_msg) from None
        else:
            archives = [archive for archive in all_archives
                        if archive.get('btype') == 'image']
            if archives:
                for archive in archives:
                    self.download_archive(build, type_path, archive, dest_dir)
            else:
                raise ValueError("No images found.") from None

    @staticmethod
    def get_remote_source_component_flat(data):
        component_type = data.get("type")
        if component_type == "gomod":
            component_type = 'GOLANG'
        elif component_type == "pip":
            component_type = "PYPI"
        elif component_type == "rubygems":
            component_type = "GEM"
        else:
            component_type = component_type.upper()
        return {
            "uuid": str(uuid.uuid4()),
            "type": component_type,
            "name": data.get("name"),
            "version": data.get("version", ""),
            "release": "",
            "summary_license": "",
            "arch": "",
            "is_source": True,
            'synced': False
        }

    def parse_remote_source_components(self, rs_archive_url):
        """
        Parse components from remote source archive url.
        """
        rs_comps = []
        try:
            data = urlopen(rs_archive_url)
            dependencies = ijson.items(data, 'dependencies.item')
            for dep in dependencies:
                comp_type = dep.get('type')
                # go-package is an abstraction over the gomod sources, not
                # exist in remote-source.tar.gz, so will not add them to
                # rs_comps list.
                if comp_type != 'go-package':
                    rs_comps.append(self.get_remote_source_component_flat(dep))
            del dependencies
        except Exception as err:
            err_msg = f"Failed to parse remote source components: {err}"
            raise RuntimeError(err_msg) from None
        return rs_comps

    def get_remote_source_components(self, build):
        """
        Get remote source components from remote source json files.
        :param build: brew build information, dict
        :return: component list of remote sources
        """
        rs_comps = []
        package_name = build.get('package_name')
        release = build.get('release')
        version = build.get('version')
        if not all([package_name, version, release]):
            raise ValueError('Cannot get the build information.') from None

        archives = self._service.listArchives(
            build.get('build_id'), type='remote-sources')
        json_archives = [a for a in archives if a.get('type_name') == 'json']
        for archive in json_archives:
            rs_path = os.path.join(
                'packages', package_name, version, release,
                'files', 'remote-sources', archive.get('filename'))
            rs_archive_url = self._format_url(rs_path)
            try:
                rs_comps.extend(
                    self.parse_remote_source_components(rs_archive_url))
            except Exception as err:
                msg = ('Failed to parse components from remote source '
                       f'archive url {rs_archive_url}: {err}.')
                raise RuntimeError(msg) from None

        if rs_comps:
            # Remove duplicate components get from remote source json files.
            grouped_comps = group_components(rs_comps, key=['name', 'version'])
            rs_comp_values = grouped_comps.values()
            rs_comps = [values[0] for values in rs_comp_values]
        return group_components(rs_comps) if rs_comps else {}

    def get_latest_source_container_build(self, binary_nvr):
        """
        Return a list of builds that match the given parameters
        Return the latest source container build according the binary NVR.

        Example:
            'binary_nvr': 'dotnet-21-container-2.1-54'
            'soruce_container_build':
                'dotnet-21-container-source-2.1-54.3'
                'dotnet-21-container-source-2.1-54.2'
                'dotnet-21-container-source-2.1-54.1'
            'latest_soruce_container_build:'
                'dotnet-21-container-source-2.1-54.3'
        """
        # 1.Get the possible source image nvr from binary image nvr
        nvr = koji.parse_NVR(binary_nvr)
        sc_name = nvr.get('name') + '-source'
        sc_nvr = "-".join((sc_name, nvr.get('version'), nvr.get('release')))
        # 2. Get the possible source image package name and package id
        package_id = self.get_package_id(sc_name)
        # 3.If the source image exists, list all the mapping source images and
        # return the latest source image.
        latest_build = ''
        if package_id:
            builds = self.list_builds(
                    package_id=package_id,
                    state=1, query_opts={'order': '-completion_time'})
            for build in builds:
                if sc_nvr in build.get('nvr'):
                    if self.get_binary_nvr(
                            build.get('nvr')) == binary_nvr:
                        latest_build = build
                        break
        return latest_build

    def download_source(self, build):
        """
        Download package build source from Brew/Koji.
        """
        temp_dir = tempfile.mkdtemp(prefix='download_')
        try:
            self.download_build_source(
                build.get('id'),
                dest_dir=temp_dir)
        except RuntimeError as err:
            err_msg = f'Failed to download source. Reason: {err}'
            raise RuntimeError(err_msg) from None
        return temp_dir

    def get_module_mapping_srpms(self, module_nvr):
        """
        Return module SRPM NVRs.
        """
        build = self.get_build(module_nvr)
        tag = build.get('extra').get('typeinfo').get('module').get(
                'content_koji_tag')
        try:
            builds = self.list_tagged(tag)
        except RuntimeError as err_msg:
            err_msg = f'Failed to get the module {module_nvr} SRPM nvrs'
            raise RuntimeError(err_msg) from None
        package_nvrs = []
        for build in builds:
            package_nvrs.append(build.get('nvr'))
        return package_nvrs

    def get_module_component(self, module_nvr):
        """
        Return module component itself.
        """
        nvr = koji.parse_NVR(module_nvr)
        return get_component_flat(nvr, 'RPMMOD')

    def get_module_srpm_components(self, module_nvr):
        """
        Get module child srpm components.
        """
        srpm_nvrs = self.get_module_mapping_srpms(module_nvr)
        srpm_components = []
        for srpm_nvr in srpm_nvrs:
            nvr = koji.parse_NVR(srpm_nvr)
            srpm_components.append(get_component_flat(nvr, 'RPM'))
        return srpm_components

    def get_module_components(self, module_nvr):
        """
        Return the group of  module components.
        """
        srpm_components = self.get_module_srpm_components(module_nvr)
        module_component = [self.get_module_component(module_nvr)]
        components = {
            'RPM': srpm_components,
            'RPMMOD': module_component
        }
        return components

    def get_task_result(self, task_id):
        return self._service.getTaskResult(task_id)

    def get_task_repository(self, build, arch="x86_64"):
        """
        Returns the task repository of the specified build, or None.

        If multiple repositories are found, only the one matches
        `arch` will be returned; If none of the repositories matches,
        the first element will be returned.
        """
        # `extra` will always be in the getBuild brew api.
        extras = build.get("extra")
        container_koji_task_id = extras.get("container_koji_task_id")
        if not container_koji_task_id:
            return None

        task_result = self.get_task_result(container_koji_task_id)
        repositories = task_result.get("repositories")
        if not repositories:
            return None

        repository = next((r for r in repositories if arch in r), None)
        if not repository:
            # use the first element in case no repo matches given arch.
            repository = repositories[0]

        return repository

    def get_source_from_registry(self, build, dest_dir):
        """
        Copy source of the source container from registry.
        """
        repository = self.get_task_repository(build)
        source_url = 'docker://' + repository
        dest = 'dir:' + dest_dir
        copy_cmd = ['skopeo', 'copy', source_url, dest]
        try:
            subprocess.check_call(copy_cmd)
        except subprocess.CalledProcessError as e:
            msg = f"Failed to copy source from registry: {e}"
            raise ValueError(msg) from None
