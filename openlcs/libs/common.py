import filetype
import glob
import mimetypes
import os
import re
import shutil
import subprocess
import time
import tarfile
import uuid
from collections import defaultdict
from itertools import groupby
from operator import itemgetter
from packageurl import PackageURL


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
    :param components: list, component list.
    :param key: list, For others, can use  key=['name', 'version'] etc.
    Example of group by 'type' by default:
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


def ungroup_components(components):
    """ # noqa
    Ungroup the components.
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
    Result:
    [
        {'name': 'github.com/blang/semver', 'type': "go-package", 'version': 'v3.5.1+incompatible', ...},
        {'name': 'github.com/hashicorp/go-syslog', 'type': "gomod", 'version': 'v1.0.0', ...},
        {'name': 'encoding/csv', 'type': "go-package", 'version': '', ...},
        {'name': 'tunnel-agent', 'type': "yarn", 'version': '0.6.0', ...},
        {'name': 'github.com/mattn/go-isatty', 'type': "gomod", 'version': 'v0.0.12', ...},
        {'name': 'umd', 'type': "yarn", 'version': '3.0.3', ...},
    ]
    """
    result = []
    for item in components.values():
        result.extend(item)
    return result


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
    version_items = component.get('version').split('/')
    name_version_items.extend(version_items)
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


def find_srpm_source(sources):
    """
    A shortcut to find the first item in `sources` that has a `purl`
    starting with "pkg:rpm" and contains "arch=src".
    Returns the matched source or None otherwise.
    """
    pattern = re.compile(r'pkg:rpm.*arch=src')
    for source in sources:
        if pattern.search(source['purl']):
            return source
    return None


# Inspired from https://stackoverflow.com/a/43319539/654952
def remove_duplicates_from_list_by_key(data, key):
    """
    Remove duplicates from a list of dictionaries based on a specific key.
    """
    seen = set()
    result = []
    for d in data:
        if d[key] not in seen:
            seen.add(d[key])
            result.append(d)
    return result


def run_and_capture(cmd, dest_dir=None):
    """
    Run a command and capture exceptions. This is a blocking call
    :cmd: str, command string
    :dest_dir: str, The current directory before the child is executed.
    :returns: tuple of exitcode, error (or None)
    :rtype: int, str | None
    """
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=dest_dir)
    _, error = proc.communicate()
    ret_code = proc.poll()
    err_msg = f"Failed to run command {cmd}: {error.decode('utf-8')}" \
        if ret_code else None
    return ret_code, err_msg


def get_extension(file_name, sp_extensions):
    """
    Return the extension of a filename. If the filename has special extension,
    like tar.gz, it also could return the right extension with tar.gz.
    """
    for extension in sp_extensions:
        if file_name.endswith(extension):
            return file_name[:-len(extension)], file_name[-len(extension):]
    return os.path.splitext(file_name)


def get_nvr_from_purl(purl):
    """
    Get nvr from parse the purl of the provide
    """
    purl_dict = PackageURL.from_string(purl).to_dict()
    nvr = '-'.join((purl_dict.get('name'),
                   purl_dict.get('version')))
    return nvr


class ExhaustibleIterator:
    """
    Extended iterator, to be able to tell if a generator is active/exhausted
    without having to consume the data.
    """
    def __init__(self, generator):
        self.generator = generator
        self.exhausted = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.exhausted:
            raise StopIteration
        try:
            return next(self.generator)
        except StopIteration:
            self.exhausted = True
            raise

    def is_exhausted(self):
        return self.exhausted

    def is_active(self):
        return not self.exhausted


def guess_env_from_principal(principal_name):
    # The worker node follows pattern below and is managed in ansible
    pattern = r"openlcs-(\w+)-worker\d+"
    match = re.search(pattern, principal_name)
    if match:
        return match.group(1).upper()
    # Hub's principal pattern starts with "openlcs-xxx" following a "."
    # see also `openlcs_route_name` in inventory/group_vars/openlcs.yml
    # in ansible roles.
    pattern = r"openlcs-(\w+)\.\w+"
    match = re.search(pattern, principal_name)
    if match:
        # Note: stage would be "stg"
        return match.group(1).upper()

    return None


def get_env():
    """
    Guess instance based on "service_principal_hostname" settings
    from the lib configuration.
    :returns: currently environment string or None
    :rtype: str | None
    """
    from .driver import load_config_to_dict
    conf = load_config_to_dict(section="general")
    principal_name = conf.get("service_principal_hostname")
    return guess_env_from_principal(principal_name) if principal_name else None


def is_prod():
    """
    Check the current environment is product or not.
    :returns: Boolean,True if `service_principal_hostname` contains "prod",
              False otherwise
    :rtype: bool
    """
    env = get_env()
    return env == "PROD" if env is not None else False


def is_shared_remote_source_need_delete(remote_source_path: str) -> bool:
    """
    Judge if a remote source dir need deleted by the
    path last access time
    Last access time more than one day will be deleted
    """
    for root, dirs, _ in os.walk(remote_source_path):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            last_access_time = os.path.getatime(dir_path)
            if time.time() - last_access_time < 60 * 60 * 24:
                return False

    return True
