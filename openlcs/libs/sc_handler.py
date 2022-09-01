import glob
import koji
import os
import sys
import uuid

# Fix absolute import issue in openlcs.
openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.common import compress_source_to_tarball  # noqa: E402


class SourceContainerHandler(object):
    """
    Object used for handle source in source containers.
    """
    def __init__(self, config=None):
        self.config = config

    @staticmethod
    def get_component_flat(data, comp_type):
        return {
            'uuid': str(uuid.uuid4()),
            'type': comp_type,
            'name': data.get('name'),
            'version': data.get('version'),
            'release': data.get('release'),
            'license': '',
            'arch': '',
            'synced': False
        }

    def get_container_component(self, sc_nvr):
        """
        Get container component.
        """
        nvr = koji.parse_NVR(sc_nvr)
        container_component = self.get_component_flat(nvr, 'CONTAINER_IMAGE')
        return container_component

    def get_srpm_components(self, srpm_dir, sc_nvr):
        """
        Get the srpm components list from source container itself. The
        component value is almost same as the srpm component from corgi.
        The value of srpm component from corgi is as following:
        {
            'uuid': 'uuid',
            'type': 'SRPM',
            'name': 'libcom_err',
            'version': '1.45.6',
            'release': '2.el8',
            'license': '',
            'arch': '',
            'synced': False
        }
        @params: srpm_dir, destination directory for srpm files' dir
        """
        components = []
        if os.path.isdir(srpm_dir):
            srpms = glob.glob(srpm_dir + "/*.src.rpm")
            for srpm in srpms:
                srpm = srpm.split('/')[-1]
                nvra = koji.parse_NVRA(srpm)
                component = {
                            'uuid': str(uuid.uuid4()),
                            'type': 'SRPM',
                            'name': nvra.get('name'),
                            'version': nvra.get('version'),
                            'release': nvra.get('release'),
                            'license': '',
                            'arch': nvra.get('arch'),
                            'synced': False
                }
                components.append(component)
            return components
        else:
            return None

    def get_source_of_srpm_component(self, srpm_dir, nvr):
        """
        Get the source file or srpm
        """
        srpm_file = nvr + '.src.rpm'
        srpm_filepath = os.path.join(srpm_dir, srpm_file)
        if os.path.isfile(srpm_filepath):
            return srpm_filepath
        else:
            return None

    def get_source_of_misc_component(self, misc_dir, nvr):
        """
        Compress the metadata files to tar file
        """
        # Named the source tar file that unified with misc component
        tar_file = nvr + '-metata.tar.gz'
        # Compress the metadata files to misc nvr tar file
        try:
            tar_filepath = os.path.join(os.path.dirname(misc_dir), tar_file)
            compress_source_to_tarball(tar_filepath, misc_dir)
        except RuntimeError as err:
            raise RuntimeError(err) from None
        return tar_filepath

    def get_container_components(self, srpm_dir, misc_dir, sc_nvr):
        """
        Get container components.
        """
        srpm_components = self.get_srpm_components(srpm_dir, sc_nvr)
        container_component = self.get_container_component(sc_nvr)
        components = {
                    'SRPM': srpm_components,
                    'CONTAINER_IMAGE': container_component
        }
        return components
