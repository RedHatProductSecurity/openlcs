import glob
import os
import pathlib
import shutil
import tarfile
import tempfile
import zipfile

from packagedcode.golang import GoModHandler
from packagedcode.npm import NpmPackageJsonHandler
from packagedcode.cargo import CargoTomlHandler
from packagedcode.rubygems import GemArchiveHandler
from packagedcode.rubygems import GemspecHandler


class MetaBase:

    SUCCESS = 0
    FAILURE = -1

    def __init__(self, source_tarball):
        self.tarball = source_tarball
        self.extensions = None
        self.metafile = None

    def _validate_tarball(self):
        if not os.path.exists(self.tarball):
            return (self.FAILURE, f"{self.tarball} does not exist.")
        if self.extensions is not None:
            extension = pathlib.Path(self.tarball).suffix
            if extension not in self.extensions:
                return (self.FAILURE, f"Unsupported file type {extension}")
        return (self.SUCCESS, "")

    def _create_temp_meta_dir(self):
        basename = os.path.basename(self.tarball)
        return tempfile.mkdtemp(prefix=f"{basename}_meta_")

    def extract_metafile_from_tgz(self):
        if self.metafile is None:
            return None
        else:
            temp_dir = self._create_temp_meta_dir()
            found = False
            with tarfile.open(self.tarball, "r:gz") as tf:
                for member in tf.getmembers():
                    if member.name.endswith(self.metafile):
                        found = True
                        tf.extract(member, temp_dir)
                        break
            return temp_dir if found else None

    def extract_metafile_from_zip(self):
        if self.metafile is None:
            return None
        else:
            temp_dir = self._create_temp_meta_dir()
            found = False
            with zipfile.ZipFile(self.tarball) as zf:
                for name in zf.namelist():
                    if name.endswith(self.metafile):
                        found = True
                        zf.extract(name, temp_dir)
                        break
            return temp_dir if found else None


class NpmMeta(MetaBase):
    def __init__(self, source_tarball):
        super().__init__(source_tarball)
        self.metafile = "package.json"
        # The default npm package archive is .tgz
        self.extensions = (".tgz",)

    def get_metadata(self, filepath):
        """
        Accept the package json filepath, returns a PackageData, None in case
        nothing is found.
        """
        # only one `PackageData` instance returned from the generator
        packages = NpmPackageJsonHandler.parse(filepath)
        return next(packages)

    def parse_metadata(self):
        """
        Returns a packagedcode "PackageData" instance when succeed,
        or a string(error message) string in case of failures.
        """
        result, message = self._validate_tarball()
        if result == self.FAILURE:
            return message
        try:
            package_json_dir = self.extract_metafile_from_tgz()
            if package_json_dir is not None:
                package_json_filepath = os.path.join(
                    package_json_dir, f"package/{self.metafile}"
                )
                return self.get_metadata(package_json_filepath)
            else:
                return None
        except StopIteration:
            return None
        finally:
            if package_json_dir is not None:
                shutil.rmtree(package_json_dir)


class GolangMeta(MetaBase):
    def __init__(self, source_tarball):
        super().__init__(source_tarball)
        self.metafile = "go.mod"
        # The default golang package archive is .zip
        self.extensions = (".zip",)

    def get_metafile_path(self, meta_dir):
        for path in glob.glob(f"{meta_dir}/**/{self.metafile}",
                              recursive=True):
            return path

    def parse_metadata(self):
        """
        Returns a packagedcode "PackageData" instance when succeed,
        or a string(error message) string in case of failures.
        """
        result, message = self._validate_tarball()
        if result == self.FAILURE:
            return message
        try:
            meta_dir = self.extract_metafile_from_zip()
            if meta_dir is not None:
                meta_filepath = self.get_metafile_path(meta_dir)
                packages = GoModHandler.parse(meta_filepath)
                return next(packages)
            else:
                return None
        except StopIteration:
            return None
        finally:
            if meta_dir is not None:
                shutil.rmtree(meta_dir)


class CargoMeta(MetaBase):
    def __init__(self, source_tarball):
        super().__init__(source_tarball)
        self.metafile = "Cargo.toml"
        self.extensions = (".crate",)

    def get_metadata(self, filepath):
        """
        Accept the package manifest filepath, returns a PackageData,
        None in case nothing is found.
        """
        packages = CargoTomlHandler.parse(filepath)
        return next(packages)

    def parse_metadata(self):
        """
        Returns a packagedcode "PackageData" instance when succeed,
        or a string(error message) string in case of failures.
        """
        result, message = self._validate_tarball()
        if result == self.FAILURE:
            return message
        try:
            meta_dir = self.extract_metafile_from_tgz()
            if meta_dir is not None:
                # Package root is where the Cargo.toml located.
                metafile_path = os.path.join(
                        meta_dir, os.listdir(meta_dir)[0], f"{self.metafile}")
                return self.get_metadata(metafile_path)
            else:
                return None
        except StopIteration:
            return None
        finally:
            if meta_dir is not None:
                shutil.rmtree(meta_dir)


class GemMeta(MetaBase):
    def __init__(self, source_tarball):
        super().__init__(source_tarball)
        self.metafile = "*.gemspec"
        self.extensions = (".gem",)

    def parse_metadata(self):
        """
        Returns a packagedcode "PackageData" instance when succeed,
        or a string(error message) string in case of failures.
        """
        package = None
        if os.path.exists(self.tarball):
            extension = pathlib.Path(self.tarball).suffix
            if extension in self.extensions:
                packages = GemArchiveHandler.parse(self.tarball)
                package = next(packages)
            # The component source is not a gem
            else:
                source_dir = os.path.dirname(self.tarball)
                metafiles = glob.glob(f"{source_dir}/**/{self.metafile}",
                                      recursive=True)
                if metafiles:
                    packages = GemspecHandler.parse(metafiles[0])
                    package = next(packages)
        return package
