import json
import subprocess
import traceback

from kobo.shortcuts import run


class BaseScanner(object):
    def __init__(self, config, src_dir=None, logger=None):
        self.config = config
        self.src_dir = src_dir
        self.logger = logger

    def get_scancode_version(self):
        scancode_cli = self.config.get('SCANCODE_CLI', '/bin/scancode')
        cmd = ('%s -V | grep -i "scancode version"' % scancode_cli)
        try:
            _, output = run(cmd, stdout=False)
        except RuntimeError:
            err_msg = 'Failed to get the scancode version used.'
            raise RuntimeError(err_msg) from None
        version = output.decode("utf-8").split(': ')[1].rstrip('\n')
        return version

    def get_scanner_version(self, scanner='scancode'):
        """
        Get the scanner together with its version used for scanning,
        default scanner is ScanCode.
        """
        get_version_method = getattr(self, 'get_' + scanner + '_version', None)
        if get_version_method is None:
            raise ValueError("No version info for %s." % scanner)
        else:
            version = get_version_method()
            self.detector = scanner + " " + version

    def scan(self, scanner='scancode'):
        self.get_scanner_version(scanner)
        scan_method = getattr(self, scanner + '_scan', None)
        if scan_method is None:
            raise ValueError("Scanner %s does not support." % self.scanner)
        else:
            return scan_method()


class LicenseScanner(BaseScanner):
    """
    Package source license detection.
    """
    def scancode_scan(self):
        scancode_license_score = self.config.get('SCANCODE_LICENSE_SCORE', 80)
        scancode_timeout = self.config.get('SCANCODE_TIMEOUT', 300)
        scancode_processes = self.config.get('SCANCODE_PROCESSES', 1)
        scancode_cli = self.config.get('SCANCODE_CLI', '/bin/scancode')

        license_list = []
        license_errors = []
        has_exception = False
        cmd = ('{} --license --license-score {} --only-findings --strip-root '
               '--processes {} --timeout {} --json - --quiet {}'.format(
                scancode_cli, scancode_license_score, scancode_processes,
                scancode_timeout, self.src_dir))

        output, error = '', ''
        try:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            output, error = proc.communicate()
        except Exception:
            has_exception = True
            license_errors.append(traceback.format_exc())
        else:
            try:
                scan_result = json.loads(output)
            except Exception:
                has_exception = True
                license_errors.append("Scancode exited with exit code {}"
                                      .format(proc.returncode))
                # There may be traceback or nothing in case scancode was killed
                if error.strip():
                    if isinstance(error, bytes):
                        error = error.decode('utf-8')
                    license_errors.append(error)
            else:
                files = scan_result.get('files', [])
                for f in files:
                    filepath = f.get('path')
                    matched_licenses = f.get('licenses')
                    if f.get('scan_errors'):
                        license_errors.append("{}: {}".format(
                            filepath, f['scan_errors']))
                    for lic in matched_licenses:
                        rid = lic['matched_rule']['identifier']
                        is_text_matched = lic['matched_rule']['is_license_text']  # noqa
                        license_list.append(
                            (filepath,
                             lic.get('spdx_license_key'),
                             lic.get('score'),
                             lic.get('start_line'),
                             lic.get('end_line'),
                             is_text_matched, rid)
                        )
                license_list = list(set(license_list))

        if self.logger is not None:
            for err_msg in license_errors:
                self.logger.error(err_msg)

        return (self.detector, license_list, license_errors, has_exception)


class CopyrightScanner(BaseScanner):
    """
    Package source copyright statement detection.
    """

    def scancode_scan(self, **options):
        """ Get the copyright statements in this package. """

        # ignore_holders = self.config.get('IGNORE_HOLDERS', [])
        # ignore_holder_pattern = "'(" + '|'.join(ignore_holders) + ")'"
        copyright_dict = {}
        copyright_errors = []
        has_exception = False

        scancode_cli = self.config.get('SCANCODE_CLI', '/bin/scancode')
        scancode_processes = self.config.get('SCANCODE_PROCESSES', 1)
        cmd = ('{} --copyright --only-findings --strip-root --tallies '
               '--processes {} --json - --quiet {}'.format(
                    scancode_cli, scancode_processes, self.src_dir))
        try:
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            output, error = proc.communicate()
        except Exception:
            has_exception = True
            copyright_errors.append(traceback.format_exc())
        else:
            try:
                scan_result = json.loads(output)
            except Exception:
                has_exception = True
                copyright_errors.append("Scancode exited with exit code {}"
                                        .format(proc.returncode))
                if error.strip():
                    if isinstance(error, bytes):
                        error = error.decode('utf-8')
                    copyright_errors.append(error)
            else:
                # Get the summary copyrights
                copyrights_tallies = scan_result['tallies']['copyrights']
                copyrights = [c.get('value') for c in copyrights_tallies]
                # Get copyright statements for each file.
                detail_copyrights = dict([
                    (f['path'], f['copyrights']) for f in scan_result['files']
                    if f['type'] == 'file' and f['copyrights']
                ])
                copyright_dict.update({
                    'summary_copyrights': list(filter(None, copyrights)),
                    'detail_copyrights': detail_copyrights,
                })
        if self.logger is not None:
            for err_msg in copyright_errors:
                self.logger.error(err_msg)

        return (self.detector, copyright_dict, copyright_errors, has_exception)
