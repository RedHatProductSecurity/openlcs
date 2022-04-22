import tempfile
import os
import sys

# Fix absolute import issue in openlcs and openlcsd.
# Import package workflow will use, test case in lib also use it.
openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.brewconn import BrewConnector  # noqa: E402


class BrewBuild:

    def __init__(self, config):
        self.brew_conn = BrewConnector(config)

    def get_build(self, package_nvr=None, tag=None, package_name=None,
                  rpm_nvra=None):
        # FIXME: raise ImproperlyConfigured Error in case we lack of
        # relevant settings on Hub.
        if package_nvr:
            build = self.brew_conn.get_build(package_nvr)
            params = package_nvr
        elif rpm_nvra:
            build = self.brew_conn.get_build_from_nvra(rpm_nvra)
            params = rpm_nvra
        elif tag and package_name:
            build = self.brew_conn.get_latest_build(tag, package_name)
            params = f"{tag} & {package_name}"
        else:
            err_msg = "Package NVR or brew tag & package name are required."
            raise ValueError(err_msg)

        if not build:
            raise RuntimeError(f'No build found for {params} in Brew.')
        return build

    def get_build_type(self, build_info):
        """
        Returns a dictionary whose keys are type names and
        whose values are the type info corresponding to that type
        """
        return self.brew_conn.get_build_type(build_info)

    def list_tagged(self, tag):
        """
        Returns a dictionary whose keys are type names and
        whose values are the type info corresponding to that type
        """
        return self.brew_conn.list_tagged(tag)

    def get_task_request(self, task_id):
        """
        Returns a list that contain the task request parameters.
        """
        return self.brew_conn.get_task_request(task_id)

    def download_source(self, build):
        """
        Download package build source from Brew.
        """
        temp_dir = tempfile.mkdtemp(prefix='download_')
        try:
            self.brew_conn.download_build_source(build.get('id'),
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
        return self.brew_conn.list_build_tags(build)

    def list_packages(self, tag_id, inherited=False):
        """
        Return a list that contain all the packages info
        corresponding to that tag id and inherited tag(if giving)
        """
        return self.brew_conn.list_packages(tag_id, inherited)

    def list_builds(self, package_id):
        """
        Return a list of builds that match the given parameters
        """
        return self.brew_conn.list_builds(package_id)
