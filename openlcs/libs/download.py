import koji
import tempfile
import os
import sys

# Fix absolute import issue in openlcs and openlcsd.
# Import package workflow will use, test case in lib also use it.
openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.kojiconnector import KojiConnector  # noqa: E402


class KojiBuild:

    def __init__(self, config):
        self.koji_connector = KojiConnector(config)

    def get_build(self, package_nvr=None, tag=None, package_name=None,
                  rpm_nvra=None):
        # FIXME: raise ImproperlyConfigured Error in case we lack of
        # relevant settings on Hub.
        if package_nvr:
            build = self.koji_connector.get_build(package_nvr)
            params = package_nvr
        elif rpm_nvra:
            build = self.koji_connector.get_build_from_nvra(rpm_nvra)
            params = rpm_nvra
        elif tag and package_name:
            build = self.koji_connector.get_latest_build(tag, package_name)
            params = f"{tag} & {package_name}"
        else:
            err_msg = "Package NVR or brew tag & package name are required."
            raise ValueError(err_msg)

        if not build:
            raise RuntimeError(f'No build found for {params} in Brew/Koji.')
        return build

    def get_build_type(self, build_info):
        """
        Returns a dictionary whose keys are type names and
        whose values are the type info corresponding to that type
        """
        return self.koji_connector.get_build_type(build_info)

    def list_tagged(self, tag):
        """
        Returns a dictionary whose keys are type names and
        whose values are the type info corresponding to that type
        """
        return self.koji_connector.list_tagged(tag)

    def get_task_request(self, task_id):
        """
        Returns a list that contain the task request parameters.
        """
        return self.koji_connector.get_task_request(task_id)

    def download_source(self, build):
        """
        Download package build source from Brew/Koji.
        """
        temp_dir = tempfile.mkdtemp(prefix='download_')
        try:
            self.koji_connector.download_build_source(
                build.get('id'),
                dest_dir=temp_dir)
        except RuntimeError as err:
            err_msg = f'Failed to download source. Reason: {err}'
            raise RuntimeError(err_msg) from None
        return temp_dir

    def list_build_tags(self, build):
        """
        Returns a list that contain all the tags info
        corresponding to that build
        """
        return self.koji_connector.list_build_tags(build)

    def list_packages(self, tag_id, inherited=False):
        """
        Return a list that contain all the packages info
        corresponding to that tag id and inherited tag(if giving)
        """
        return self.koji_connector.list_packages(tag_id, inherited)

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
        package_id = self.koji_connector.get_package_id(sc_name)
        # 3.If the source image exists, list all the mapping source images and
        # return the latest source image.
        latest_build = ''
        if package_id:
            builds = self.koji_connector.list_builds(
                    package_id=package_id,
                    state=1, query_opts={'order': '-completion_time'})
            for build in builds:
                if sc_nvr in build.get('nvr'):
                    if self.koji_connector.get_binary_nvr(
                            build.get('nvr')) == binary_nvr:
                        latest_build = build
                        break
        return latest_build
