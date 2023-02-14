import filetype
import glob
import mimetypes
import os
import re
import shutil
import subprocess
import tarfile
import uuid
from collections import defaultdict
from itertools import groupby
from operator import itemgetter


def get_mime_type(filepath):
    mime_type = mimetypes.MimeTypes().guess_type(filepath)[0]
    if not mime_type:
        try:
            mime_type = filetype.guess_mime(filepath)
        except TypeError:
            pass
    return mime_type


def create_dir(directory):
    """
    Create a directory to store non source RPMs files.
    """
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory, ignore_errors=True)
        os.makedirs(directory)
        if not os.path.exists(directory):
            err_msg = f"Failed to create directory: {directory}"
            raise RuntimeError(err_msg)
    except Exception as err:
        raise RuntimeError(err) from None
    return directory


def uncompress_source_tarball(src_file, dest_dir=None):
    """
    Uncompress source tarball to destination directory,
    and remove the source tarball.
    """
    try:
        t = tarfile.open(src_file)
        dest_dir = os.path.dirname(src_file) if not dest_dir else dest_dir
        t.extractall(path=dest_dir)
    except Exception as err:
        err_msg = f"Failed to uncompress source tarball: {err}."
        raise ValueError(err_msg) from None
    else:
        os.remove(src_file)


def group_components(components, key=None):
    """ # noqa
    Group by the remote source components.
    Example of group by 'type':
    [
        {'name': 'github.com/blang/semver', 'type': "go-package", 'version': 'v3.5.1+incompatible', ...},
        {'name': 'github.com/hashicorp/go-syslog', 'type': "gomod", 'version': 'v1.0.0', ...},
        {'name': 'encoding/csv', 'type': "go-package", 'version': '', ...},
        {'name': 'tunnel-agent', 'type': "yarn", 'version': '0.6.0', ...},
        {'name': 'github.com/mattn/go-isatty', 'type': "gomod", 'version': 'v0.0.12', ...},
        {'name': 'umd', 'type': "yarn", 'version': '3.0.3', ...},
    ]
    Result:
    {
        'go-package': [
            {'name': 'github.com/blang/semver', 'type': 'go-package', 'version': 'v3.5.1+incompatible', ...},
            {'name': 'encoding/csv', 'type': 'go-package', 'version': '', ...}
        ],
        'gomod': [
            {'name': 'github.com/hashicorp/go-syslog', 'type': 'gomod', 'version': 'v1.0.0', ...},
            {'name': 'github.com/mattn/go-isatty', 'type': 'gomod', 'version': 'v0.0.12', ...}
        ],
        'yarn': [
            {'name': 'tunnel-agent', 'type': 'yarn', 'version': '0.6.0', ...},
            {'name': 'umd', 'type': 'yarn', 'version': '3.0.3', ...}
        ]
    }
    """
    result = defaultdict(list)
    key = key if key else ['type']
    for key, items in groupby(components, key=itemgetter(*key)):
        for i in items:
            result[key].append(i)
    return dict(result)


def compress_source_to_tarball(dest_file, src_dir, remove_source=True):
    """
    Compress source in the directory to tar.gz file,
    and remove the source directory.
    """
    try:
        # Using this command to make sure source tarball same
        # checksum if compress same source.
        cmd = "tar -c  * | gzip -n > %s" % dest_file
        subprocess.check_call(cmd, shell=True, cwd=src_dir)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e) from None
    else:
        if remove_source:
            shutil.rmtree(src_dir)


def get_component_name_version_combination(component):
    """
    Get a combination of name, version in component.
    """
    name_version_items = component.get('name').split('/')
    name_version_items.append(component.get('version'))
    return '-'.join(name_version_items)


def get_nvr_list_from_components(components, comp_type):
    """
    Get a nvr list of components.
    """
    nvr_list = []
    components = components.get(comp_type)
    if components:
        for component in components:
            if component.get('release'):
                nvr = "{name}-{version}-{release}".format(**component)
            else:
                nvr = "{name}-{version}".format(**component)
            nvr_list.append(nvr)
    return nvr_list


def search_content_by_patterns(search_patterns):
    """
    Search content by the giving patterns.
    """
    paths = []
    if search_patterns:
        for search_pattern in search_patterns:
            paths = glob.glob(search_pattern, recursive=True)
            if paths:
                break
    return paths


def selection_sort_components(components):
    """
    Sort components by the component name.
    """
    length = len(components)
    for i in range(length - 1, 0, -1):
        for j in range(i):
            if components[j].get('name') in components[i].get('name'):
                components[j], components[i] = components[i], components[j]
    return components


def get_component_flat(data, comp_type):
    component = {
            'uuid': str(uuid.uuid4()),
            'type': comp_type,
            'name': data.get('name'),
            'version': data.get('version'),
            'release': data.get('release'),
            'summary_license': '',
            'synced': False
        }
    if comp_type == 'RPMMOD':
        component.update({'arch': ''})
    else:
        component.update({'arch': 'src', 'is_source': True})
    return component


def uncompress_blob_gzip_files(src_file, dest_dir):
    # Uncompress the blob files that come from source container registry.
    # Under the directory, most of the files are gzip files that need to
    # decompress. There are some metadata files that no need to decompress.
    err_msg_list = []
    src_dir = os.path.dirname(src_file)
    blob_files = os.listdir(src_dir)
    for blob_file in blob_files:
        blob_file = os.path.join(src_dir, blob_file)
        file_type = get_mime_type(blob_file)
        if file_type == "application/gzip":
            cmd = ['tar', '-xvf', blob_file]
            try:
                subprocess.check_call(cmd, cwd=dest_dir)
            except Exception as e:
                err_msg = f"Failed to decompress blob files: {e}"
                err_msg_list.append(err_msg)
            else:
                os.remove(blob_file)
        continue
    return err_msg_list


def find_srpm_source(sources:list[dict]):
    """
    A shortcut to find the first item in `sources` that has a `purl`
    starting with "pkg:rpm" and contains "arch=src".
    Returns the "link" of matched source or None otherwise.
    """
    pattern = re.compile(r'pkg:rpm.*arch=src')
    for source in sources:
        if pattern.search(source['purl']):
            return source['link']
    return None
