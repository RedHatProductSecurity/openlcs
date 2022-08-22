import os
import shutil
import subprocess


def create_dir(directory):
    """
    Create a directory to store non source RPMs files.
    """
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory, ignore_errors=True)
        os.makedirs(directory)
    except Exception as e:
        raise RuntimeError(e) from None
    return directory


def compress_source_to_tarball(dest_file, src_dir):
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
        shutil.rmtree(src_dir)


def get_nvr_list_from_components(components, comp_type):
    nvr_list = []
    for component in components.get(comp_type):
        nvr = "{name}-{version}-{release}".format(**component)
        nvr_list.append(nvr)
    return nvr_list
