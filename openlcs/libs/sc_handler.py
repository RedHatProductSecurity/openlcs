import glob
import koji
import os
import re
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
    get_component_flat,
    get_component_name_version_combination,
    search_content_by_patterns,
    uncompress_blob_gzip_files,
    uncompress_source_tarball,
    selection_sort_components
)


CORGI_OSBS_RS_TYPE_MAPPING = {
    'GOLANG': 'gomod',
    'NPM': 'npm',
    'YARN': 'yarn',
    'PYPI': 'pip',
    'CARGO': 'cargo',
    'GEM': 'rubygems'
}
RS_TARBALL_EXTENSIONS = [
    '.tgz',
    '.tar.gz',
    '.zip',
    '.gem',
    '.crate'
]


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

    def get_container_component(self, sc_nvr):
        """
        Get container component.
        """
        nvr = koji.parse_NVR(sc_nvr)
        return get_component_flat(nvr, 'OCI')

    def get_srpm_components(self, srpm_dir):
        """
        Get the srpm components list from source container itself. The
        component value is almost same as the srpm component from corgi.
        The value of srpm component from corgi is as following:
        {
            'uuid': 'uuid',
            'type': 'RPM',
            'name': 'libcom_err',
            'version': '1.45.6',
            'release': '2.el8',
            'summary_license': '',
            'arch': 'src',
            'is_source': True,
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
                    'type': 'RPM',
                    'name': nvra.get('name'),
                    'version': nvra.get('version'),
                    'release': nvra.get('release'),
                    'summary_license': '',
                    'arch': nvra.get('arch'),
                    'is_source': True,
                }
                components.append(component)
        return components

    @staticmethod
    def get_source_of_srpm_component(srpm_dir, nvr):
        """
        Get the source file or srpm
        """
        srpm_file = nvr + '.src.rpm'
        srpm_filepath = os.path.join(srpm_dir, srpm_file)
        return srpm_filepath if os.path.isfile(srpm_filepath) else None

    @staticmethod
    def get_source_of_remote_source_components(rs_dir, component):
        """
        Get the source tarball for remote source components.
        """
        name_version = get_component_name_version_combination(component)
        name_version_dir = os.path.join(rs_dir, name_version)
        rs_tarballs = os.listdir(name_version_dir)
        if rs_tarballs:
            tarball_name = os.listdir(name_version_dir)[0]
            return os.path.join(name_version_dir, tarball_name)
        else:
            return None

    def get_container_components(self, srpm_dir, sc_nvr):
        """
        Get container components.
        """
        srpm_components = self.get_srpm_components(srpm_dir)
        container_component = [self.get_container_component(sc_nvr)]
        components = {
            'RPM': srpm_components,
            'OCI': container_component
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
            link_path = ""
            for extra_tarball_path in extra_tarball_paths:
                if os.path.islink(extra_tarball_path):
                    link_path = os.readlink(extra_tarball_path)
                uncompress_source_tarball(extra_tarball_path)

                # Remove remote source tarball, so that it will not
                # exist in misc source.
                if link_path:
                    full_path = os.path.normpath(
                        os.path.join(
                            os.path.dirname(extra_tarball_path),
                            link_path
                        )
                    )
                    os.remove(full_path)

            # uncompress remote source tarballs in extra source tarballs.
            rs_tarball_paths = glob.glob(f"{rs_dir}/*.tar.gz")
            for rs_tarball_path in rs_tarball_paths:
                rs_tarball_name = os.path.basename(rs_tarball_path).replace(
                    '.tar.gz', "")
                rs_dest_dir = os.path.join(rs_dir, rs_tarball_name)
                uncompress_source_tarball(rs_tarball_path, rs_dest_dir)
        return rs_dir

    def get_source_container_metadata(self):
        """
        Get metadata files of source RPMs in source container.
        """
        misc_dir = os.path.join(self.dest_dir, 'metadata')
        misc_dir = create_dir(misc_dir)

        # Remove all the "layer.tar" files, because they are unuseful
        # soft link files.
        layer_file_paths = glob.glob(self.dest_dir + '/**/layer.tar')
        for layer_file_path in layer_file_paths:
            os.remove(layer_file_path)

        # Move all the misc files, directories to "metadata" directory.
        dest_nested_items = os.listdir(self.dest_dir)
        src_dir = os.path.dirname(self.src_file)
        src_nested_items = os.listdir(src_dir)
        item_paths = []
        for nested_item in dest_nested_items:
            if nested_item not in ['extra_src_dir', 'rpm_dir', 'metadata']:
                item_paths.append(os.path.join(self.dest_dir, nested_item))
        # Move all the metadata files from src_dir to metadata directory for
        # getting container source from registry.
        for nested_item in src_nested_items:
            item_paths.append(os.path.join(src_dir, nested_item))
        for item_path in item_paths:
            shutil.move(item_path, misc_dir)

        return misc_dir

    def unpack_source_container_image(self):
        """
        Unpack source container image to destination directory.
        """
        # No need to uncompress source container image if the source could
        # get from the registry. Because the source blob files are
        # located in the downloaded directory, no longer in docker image.
        errs = []
        if 'docker_image' in self.src_file:
            uncompress_source_tarball(self.src_file, self.dest_dir)
            tarballs = glob.glob(f"{self.dest_dir}/*.tar")
            for tarball in tarballs:
                uncompress_source_tarball(tarball)
        else:
            errs = uncompress_blob_gzip_files(self.src_file, self.dest_dir)
        # Get source RPMs in the source container.
        srpm_dir = self.get_source_container_srpms()

        # Unpack each remote source tarball.
        rs_dir = self.unpack_source_container_remote_source()

        # Get metadata files of source RPMs to metadata dir, will add the
        # remote source metadata in this directory at the other steps.
        misc_dir = self.get_source_container_metadata()

        return srpm_dir, rs_dir, misc_dir, errs

    @staticmethod
    def get_component_search_items(component):
        """
        Get the search items of the component.
        """
        comp_type = component.get('type')
        if comp_type == 'GOLANG':
            # If the name contains Uppercase, will convert it to "!" + it's
            # lowercase in the source tarball path. Reference link:
            # https://pkg.go.dev/golang.org/x/mod/module#hdr-Escaped_Paths
            search_name = ''.join([s.isupper() and "!" + s.lower() or s
                                   for s in component.get('name')])
            name_items = search_name.split("/")
            # ":", "/", "#" maybe in the version string.
            version_items = re.split("[:/#]", component.get('version'))
        elif comp_type in ['NPM', 'YARN', 'PYPI', 'CARGO', 'GEM']:
            search_name = component.get('name')
            name_items = component.get('name').replace("@", '').split("/")
            # ":", "/", "#" maybe in the version string.
            version_items = re.split("[:/#]", component.get('version'))
        else:
            err_msg = (f'Currently we do not support {comp_type} type of '
                       f'remote source.')
            raise RuntimeError(err_msg)
        return search_name, name_items, version_items

    def get_remote_source_search_patterns(self, component, extra_src_dir):
        """
        Get all possible matching patterns for the component.
        """
        search_name, name_items, version_items = \
            self.get_component_search_items(component)
        comp_type = component.get('type')
        name_pattern = '/*' + '/'.join(name_items)
        version_pattern = '/*' + '*'.join(version_items)
        search_patterns = ""

        # The extensions of remote source tarball:
        # 'gomod' tarball is '.zip', 'npm' tarball is '.tgz',
        # 'yarn' tarball is '.tgz', 'pip' tarball is '.tar.gz'.
        # 'rubygems' tarball is '.gem'
        if comp_type == 'GOLANG':
            dep_dir_pattern = os.path.join(
                extra_src_dir, "**", "deps", 'gomod', "pkg",
                "mod", "cache", "download")
            vendor_pattern = extra_src_dir + "/**/app/vendor"
            # Exist new version, such as:
            # 'deps/gomod/pkg/mod/cache/download/k8s.io/klog/@v/v1.0.0.zip'
            # 'deps/gomod/pkg/mod/cache/download/k8s.io/klog/v2/@v/v2.9.0.zip'
            search_patterns = [
                dep_dir_pattern + name_pattern + "/@v" + version_pattern + '.zip',  # noqa
                dep_dir_pattern + name_pattern + "/**/@v" + version_pattern + '.zip',  # noqa
                vendor_pattern + "/" + search_name
            ]
            # Use the original name in app vendor source path.
            component_name = component.get('name')
            if search_name != component_name:
                search_patterns.append(vendor_pattern + "/" + component_name)
        elif comp_type in ['NPM', 'YARN']:
            # YARN type in brew can be NPM type in corgi
            search_patterns = []
            for comp_type in [CORGI_OSBS_RS_TYPE_MAPPING['NPM'],
                              CORGI_OSBS_RS_TYPE_MAPPING['YARN']]:
                dep_dir_pattern = os.path.join(
                    extra_src_dir, '**', 'deps', comp_type)
                common_pattern = dep_dir_pattern + name_pattern \
                    + version_pattern
                search_patterns.extend(
                    [common_pattern + extension
                     for extension in RS_TARBALL_EXTENSIONS]
                )
        elif comp_type in ['PYPI', 'CARGO', 'GEM']:
            # mapping remote source between Corgi and OSBS
            comp_type = CORGI_OSBS_RS_TYPE_MAPPING.get(comp_type)
            dep_dir_pattern = os.path.join(
                extra_src_dir, '**', 'deps', comp_type)
            common_pattern = dep_dir_pattern + name_pattern + version_pattern
            search_patterns = [common_pattern + extension
                               for extension in RS_TARBALL_EXTENSIONS]
        return search_patterns

    def get_special_component_path(self, component, extra_src_dir):
        comp_type = component.get('type')
        comp_version = component.get('version')
        comp_type = CORGI_OSBS_RS_TYPE_MAPPING.get(comp_type)
        dep_dir_pattern = os.path.join(extra_src_dir, '**', 'deps', comp_type)
        _, name_items, version_items = self.get_component_search_items(
            component)
        name_pattern = '/*' + '/'.join(name_items) + '*'
        version_pattern = '/*' + '*'.join(version_items)

        # For the git commit hash in the component version.
        # Example:
        # Component in quay-registry-container-v3.7.7-6
        # {
        #     "dev": false,
        #     "name": "aniso8601",
        #     "replaces": null,
        #     "type": "pip",
        #     "version": "git+https://github.com/DevTable/aniso8601-fake.git@bd7762c7dea0498706d3f57db60cd8a8af44ba90"  # noqa
        # }
        # Component in console-api-container-v2.1.2-2
        # {
        #     "dev": false,
        #     "name": "security-middleware",
        #     "replaces": null,
        #     "type": "npm",
        #     "version": "github:open-cluster-management/security-middleware#f88cdf9595326722109baac72e7af1f543014683"  # noqa
        # },
        for char in ['@', '#']:
            if char in comp_version and re.match(r'[0-9a-f]{40}', (
                    comp_commit := comp_version.split(char)[-1])):
                version_pattern = '/*' + comp_commit
        # For sha256 string in the component version.
        # Component in quay-registry-container-v3.7.7-6
        # {
        #     "dev": false,
        #     "name": "PyPDF2",
        #     "replaces": null,
        #     "type": "pip",
        #     "version": "https://files.pythonhosted.org/packages/3d/48/0966606e08dd93a77e839803789151ff81ac27ec6767957af8afb9588501/PyPDF2-1.27.6.tar.gz#egg=PyPDF2&cachito_hash=sha256:3a3c0585678279b93a4c0fa31fb6f6217cfbdac3f6d3dcd1dfc9888579f3e858"  # noqa
        # },
        if ':' in comp_version and re.match(r'[0-9a-f]{64}', (
                comp_commit := comp_version.split(':')[-1])):
            version_pattern = '/*' + comp_commit
        # Using name pattern and version pattern to search source path.
        search_patterns = [
            dep_dir_pattern + "/**" + name_pattern + version_pattern + extension  # noqa
            for extension in RS_TARBALL_EXTENSIONS
        ]
        # Only use version pattern to search source path.
        search_patterns.extend([
            dep_dir_pattern + "/**" + version_pattern + extension
            for extension in RS_TARBALL_EXTENSIONS
        ])

        paths = search_content_by_patterns(search_patterns)
        return paths[0] if paths else None

    def get_remote_source_path(self, component, extra_src_dir):
        """
        Get source tarball path of the remote source component.
        """
        search_patterns = self.get_remote_source_search_patterns(
            component, extra_src_dir)

        # Search remote source path.
        paths = search_content_by_patterns(search_patterns)
        source_path = None
        if paths:
            # Find the correct source path.
            if len(paths) == 1:
                source_path = paths[0]
            # Exist components with same name, but different version.
            # Currently, only find this scenario exists for GOLANG components.
            else:
                comp_name = component.get('name')
                comp_version = component.get('version')
                comp_type = component.get('type')
                check_str = comp_name + " " + comp_version
                for path in paths:
                    # Exist many source paths in "app/vendor".
                    if "/app/vendor/" in path:
                        app_path = path[:path.index('vendor')]
                        modules_file_path = os.path.join(
                            app_path, 'vendor', 'modules.txt')
                        with open(modules_file_path, encoding='utf8') as f:
                            if check_str in f.read():
                                source_path = path
                                break
                    # Exist many source paths in "deps".
                    elif "/deps/" in path and comp_type == 'GOLANG':
                        modules_file_path = os.path.join(
                            os.path.dirname(path), comp_version + ".mod")
                        if os.path.exists(modules_file_path):
                            source_path = path
                            break
                    # Exist two json file with same component, each one has
                    # the relative source. For this scenario, use one of them.
                    else:
                        source_path = path
                        break
        else:
            # Add patterns for some special components that name, version
            # mismatch with source path in source container. More detail,
            # check PELC-4511, CLOUDBLD-3809, and OLCS-292.
            source_path = self.get_special_component_path(
                component, extra_src_dir)
        return source_path, search_patterns

    def get_container_remote_source(self, components):
        """
        Get remote source in source container.
        """
        missing_components = []
        missing_components_error = []
        extra_src_dir = os.path.join(self.dest_dir, 'extra_src_dir')

        if os.path.exists(extra_src_dir):
            # Sort components so that not remove the source needed by other
            # components.
            components = selection_sort_components(components)

            # Get source for each component.
            for _ in range(len(components)):
                component = components.pop(0)
                comp_path, search_patterns = self.get_remote_source_path(
                    component, extra_src_dir)
                if not comp_path:
                    missing_components.append(component)
                    err_msg = (f"Failed to get remote source for component."
                               f"Error info:can not find source tarball path,"
                               f" search path:{extra_src_dir}, search patterns"
                               f":{search_patterns}.Component info:"
                               f"{component}")
                    missing_components_error.append(err_msg)
                    continue

                # Create a directory to store remote source tarball.
                name_version = get_component_name_version_combination(
                    component)
                comp_dir = os.path.join(self.dest_dir, 'rs_dir', name_version)
                create_dir(comp_dir)

                # Handle source when found it in app vendor, compress the
                # source as a source tarball.
                if os.path.isdir(comp_path):
                    try:
                        dest_path = os.path.join(
                            comp_dir, name_version + ".tar.gz")
                        # Check if the source is child component source. For
                        # this scenario, cannot remove the source, the source
                        # will be reused by parent component.
                        # TODO: the policy here should be refined. This way
                        # the same source will be scanned twice, the parent's
                        # result could be summarized from its children nodes.
                        comp_name = component.get('name')
                        comp_type = component.get('type')
                        if any([comp_name.startswith(
                                c.get('name') + os.sep) and c.get(
                                'type') == comp_type for c in components]):
                            remove_source = False
                        else:
                            remove_source = True
                        compress_source_to_tarball(
                            dest_path, comp_path, remove_source=remove_source)
                    except RuntimeError as err:
                        err_msg = (f"Failed to compress {component} source in "
                                   f"app vendor: {err}")
                        raise RuntimeError(err_msg) from None
                else:
                    # Move source tarball to destination directory.
                    shutil.move(comp_path, comp_dir)

            # Handle misc data in remote source.
            misc_dir = os.path.join(self.dest_dir, 'metadata')
            shutil.move(extra_src_dir, misc_dir)
        else:
            err_msg = (f"Failed to get remote source for components."
                       f"Error info: extra_src_dir:{extra_src_dir} not exist."
                       f"Components info:{components}")
            missing_components_error.append(err_msg)
            missing_components = components

        return missing_components, missing_components_error

    @staticmethod
    def get_shared_remote_source_root_dir(tmp_root_dir, parent_component):
        return os.path.join(
            tmp_root_dir,
            "shared_remote_source_root",
            parent_component["name"],
            parent_component["version"],
            parent_component["release"]
        )
