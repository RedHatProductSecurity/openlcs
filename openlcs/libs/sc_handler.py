import glob
import koji
import os
import sys
import shutil
import uuid

# Fix absolute import issue in openlcs.
openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.common import (  # noqa: E402
    compress_source_to_tarball,
    create_dir,
    uncompress_source_tarball
)


class SourceContainerHandler(object):
    """
    Object used for handle source in source containers.
    @params: src_file, absolute filepath. e.g., /tmp/foo-1.1-0.rpm
    @params: dest_dir, destination directory to which the unpacked sources
    will be moving to.
    """
    def __init__(self, config=None, src_file=None, dest_dir=None):
        self.config = config
        self.src_file = src_file
        self.dest_dir = dest_dir

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
        container_component = [self.get_component_flat(nvr, 'CONTAINER_IMAGE')]
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

    def get_source_container_srpms(self):
        """
        Get the source RPMs in source container.
        """
        source_dir = os.path.join(self.dest_dir, "blobs", "sha256")
        soft_link_dir = os.path.join(self.dest_dir, 'rpm_dir')
        if os.path.exists(soft_link_dir):
            srpm_names = os.listdir(soft_link_dir)
            for srpm_name in srpm_names:
                try:
                    soft_link_path = os.path.join(soft_link_dir, srpm_name)
                    sha256_str = os.path.basename(os.readlink(soft_link_path))
                    sha256_path = os.path.join(source_dir, sha256_str)
                    shutil.move(sha256_path, soft_link_path)
                except OSError as err:
                    err_msg = f"Failed to collate source RPM {srpm_name}:{err}"
                    raise RuntimeError(err_msg) from None
        return soft_link_dir

    def unpack_source_container_remote_source(self):
        """
        Unpack remote source in source container.
        """
        rs_dir = os.path.join(self.dest_dir, 'extra_src_dir')
        if os.path.exists(rs_dir):
            # uncompress extra source tarballs.
            extra_tarball_paths = glob.glob(f"{rs_dir}/*.tar")
            for extra_tarball_path in extra_tarball_paths:
                uncompress_source_tarball(extra_tarball_path)

            # uncompress remote source tarballs in extra source tarballs.
            rs_tarball_paths = glob.glob(f"{rs_dir}/*.tar.gz")
            for rs_tarball_path in rs_tarball_paths:
                uncompress_source_tarball(rs_tarball_path)
        return rs_dir

    def get_source_container_srpms_metadata(self):
        """
        Get metadata files of source RPMs in source container.
        """
        misc_dir = os.path.join(self.dest_dir, 'metadata')
        misc_dir = create_dir(misc_dir)
        patterns = ['/*.json', '/repositories']
        for pattern in patterns:
            misc_files = glob.glob(self.dest_dir + pattern)
            for file in misc_files:
                shutil.move(file, misc_dir)
        return misc_dir

    def unpack_source_container_image(self):
        """
        Unpack source container image to destination directory.
        """
        # uncompress source container image.
        uncompress_source_tarball(self.src_file, self.dest_dir)
        tarballs = glob.glob(f"{self.dest_dir}/*.tar")
        for tarball in tarballs:
            uncompress_source_tarball(tarball)

        # Get source RPMs in the source container.
        srpm_dir = self.get_source_container_srpms()

        # Unpack each remote source tarball.
        rs_dir = self.unpack_source_container_remote_source()

        # Get metadata files of source RPMs to metadata dir, will add the
        # remote source metadata in this directory at the other steps.
        misc_dir = self.get_source_container_srpms_metadata()

        return srpm_dir, rs_dir, misc_dir
