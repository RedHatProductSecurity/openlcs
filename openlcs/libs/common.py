import filetype
import mimetypes
import os
import shutil
import subprocess
import tarfile


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
