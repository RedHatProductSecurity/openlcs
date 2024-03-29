import os
import shutil
import tempfile
import traceback
from kobo.shortcuts import run
from .common import (
    get_mime_type, get_extension,
    run_and_capture,
    search_content_by_patterns
)


SUPPORTED_FILE_EXTENSIONS = [
        '.tar.gz', '.tgz', '.tar.bz', '.tbz', '.tar.bz2', '.tbz2', '.tar.Z',
        '.tZ', '.tar.lzo', '.tzo', '.tar.lz', '.tlz', '.tar.xz', '.txz',
        '.tar.7z', '.t7z', '.tar', '.zip', '.jar', '.war', '.rar', '.lha',
        '.lzh', '.7z', '.alz', '.ace', '.a', '.arj', '.arc', '.rpm', '.deb',
        '.cab', '.gz', '.bz', '.bz2', '.Z', '.lzma', '.lzo', '.lz', '.xz',
        '.rz', '.lrz', '.7z', '.cpio'
]

SP_EXTENSIONS = [
        '.tar.gz', '.tar.bz', '.tar.bz2', '.tar.Z', '.tar.lzo', '.tar.lz',
        '.tar.xz', '.tar.7z'
]


class UnpackArchive(object):
    """
    @params: config, configuration related to unpack function.
    @params: src_file, absolute filepath. e.g., /tmp/foo-1.1-0.rpm
    @params: dest_dir, destination directory to which the unpacked sources
    will be moving to.
    """
    def __init__(self, config=None, src_file=None, dest_dir=None):
        self.config = config
        self.src_file = src_file
        self.dest_dir = dest_dir

    def _get_archive_type(self):
        """
        Identify source type from mime.
        """
        return get_mime_type(self.src_file)

    def _extract_rpm(self):
        """
        Extract source rpm into directory src_dir.
        """
        cmd = ('rpm2cpio %s | cpio -idm --quiet' % self.src_file)
        try:
            run(cmd, stdout=False, workdir=self.dest_dir)
        except RuntimeError as e:
            err_msg = 'Error while extracting files from %s. Reason: %s' % (
                    self.src_file, e)
            raise RuntimeError(err_msg) from None

    def _extract_non_rpm(self, mime_type):
        """
        Extract non-rpm source archive into directory src_dir.
        """
        # For non-rpm package source, copy source archive directly
        shutil.copy(self.src_file, self.dest_dir)

    def extract(self):
        """
        Extract source archive into directory src_dir.
        """
        if not self.src_file:
            raise AttributeError('Missing source archive file.')
        if self.dest_dir is None:
            self.dest_dir = tempfile.mkdtemp(prefix='src_')
        mime_type = self._get_archive_type()

        try:
            if mime_type == 'application/x-rpm':
                self._extract_rpm()
            else:
                self._extract_non_rpm(mime_type)
        except RuntimeError as e:
            fname = os.path.basename(self.src_file)
            err_msg = 'Failed to extract source archive %s. Reason: %s' % (
                    fname, e)
            raise RuntimeError(err_msg) from None

    @staticmethod
    def unpack_file(file_name, main_dir=None):
        """
        Extracts given file to a temporary directory.
        If the file is an archive, returns path to directory with extracted
        content. If the file is an unknown archive or text file returns None.
        In case of error raises ValueError.
        """
        abs_path = os.path.abspath(file_name)
        file_name = os.path.basename(file_name)
        file_path = main_dir or os.path.dirname(abs_path)
        _, file_extension = get_extension(file_name, SP_EXTENSIONS)
        if file_extension in SUPPORTED_FILE_EXTENSIONS:
            tmp_dir = tempfile.mkdtemp(prefix='tmpunpack_', dir=main_dir)
            cmd = ("atool -X '%(tmp_dir)s' -q '%(file_path)s/%(file_name)s' "
                   ">/dev/null" % locals())
            try:
                run(cmd, workdir=file_path)
                return tmp_dir
            except RuntimeError:
                shutil.rmtree(tmp_dir)
                err_msg = 'Unable to decompress file %s.' % file_name
                raise ValueError(err_msg) from None

    def unpack_archives_using_extractcode(self, src_dir=None,
                                          shallow=False, rm=True):
        """
        Unpack the source archives in src_dir directory using extractcode.
        """
        error = ""
        extract_cli = self.config.get(
            'EXTRACTCODE_CLI', '/bin/extractcode')
        raw_src_list = os.listdir(src_dir) if rm else []
        # Running extractcode with '--replace-originals' may crash:
        # https://github.com/nexB/scancode-toolkit/issues/2723
        # The fix below is not online yet:
        # https://github.com/nexB/extractcode/commit/8c8653645648e04e94f1ae13e00bd477284dac8e  # noqa
        if shallow:
            cmd = f'{extract_cli} --replace-originals --shallow {src_dir}'
        else:
            cmd = f'{extract_cli} --replace-originals {src_dir}'
        try:
            _, error = run_and_capture(cmd)
        except Exception:
            if rm:
                for fn in os.listdir(src_dir):
                    if fn not in raw_src_list:
                        fpath = os.path.join(src_dir, fn)
                        shutil.rmtree(fpath, ignore_errors=False)
            error = "Failed to unpack source archives in {} using " \
                    "extractcode: {}".format(src_dir, traceback.format_exc())
        return error

    def unpack_archives_using_atool(self, src_dir, top_dir=False):
        """
        Unpack all archives in src_dir directory using atool.
        """
        errors = []
        for root, _, files in os.walk(src_dir):
            if top_dir:
                for fn in files:
                    try:
                        tmp = self.unpack_file(fn, main_dir=root)
                        if tmp:
                            # Delete the archive file after unpack
                            os.remove(os.path.join(root, fn))
                            # Rename the root tmp directory to tarball name to
                            # keep consistency with format from extractcode
                            new_root = os.path.join(root, fn)
                            os.rename(tmp, new_root)
                            errors.extend(self.unpack_archives(new_root))
                    except ValueError as e:
                        errors.append(str(e))
            else:
                # In case of root directory is a temporarily created one.
                # Move all files under root to its parent.
                parent_dir = os.path.abspath(os.path.join(src_dir, os.pardir))
                for f in os.listdir(src_dir):
                    if os.path.exists(os.path.join(parent_dir, f)):
                        parent_dir = tempfile.mkdtemp(
                            suffix='-atool', dir=parent_dir)
                    shutil.move(os.path.join(root, f), parent_dir)

                for fn in files:
                    try:
                        tmp = self.unpack_file(fn, main_dir=parent_dir)
                        if tmp:
                            # Delete the archive file after unpack
                            os.remove(os.path.join(parent_dir, fn))
                            errors.extend(self.unpack_archives(tmp))
                    except ValueError as e:
                        errors.append(str(e))

        # Remove temporarily created folders.
        if not top_dir:
            shutil.rmtree(src_dir)
        return errors

    def unpack_archives(self, src_dir=None):
        """
        Unpack the source archives in src_dir directory.
        """
        errors = []
        src_dir = self.dest_dir if src_dir is None else src_dir
        raw_src_list = os.listdir(src_dir)
        raw_error = self.unpack_archives_using_extractcode(src_dir)
        if raw_error:
            if isinstance(raw_error, bytes):
                error = raw_error.decode('utf-8')
                errors.append(error)
                # Skip extracting errors for testing archives
                extract_errors = [
                    e for e in error.split('\n') if 'ERROR extracting:' in e]
                test_errors = [
                    e for e in extract_errors if '/testdata/' in e]
                if extract_errors and len(extract_errors) == len(test_errors):
                    patterns = [f"{src_dir}/**/*-extract"]
                    paths = search_content_by_patterns(patterns)
                    sorted_paths = sorted(
                        paths, key=lambda p: (-p.count(os.path.sep), p))
                    for path in sorted_paths:
                        target = path.rstrip('-extract')
                        if os.path.exists(target):
                            os.remove(target)
                        os.rename(path, target)
                    return errors
            else:
                errors.append(raw_error)
            for fn in os.listdir(src_dir):
                if fn not in raw_src_list:
                    fpath = os.path.join(src_dir, fn)
                    shutil.rmtree(fpath, ignore_errors=False)
            errors.extend(
                self.unpack_archives_using_atool(src_dir, top_dir=True))
        return errors
