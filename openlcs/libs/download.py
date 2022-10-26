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
        """
        Shortcut to get build using various forms.
        """
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
