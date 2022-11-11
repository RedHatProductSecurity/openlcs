import glob
import os
import shutil
import tarfile
import tempfile
import zipfile

from packagedcode.golang import GolangPackage
from packagedcode.npm import parse


class MetaBase:
    def __init__(self, source_tarball):
        self.tarball = source_tarball

    def _create_temp_meta_dir(self):
        basename = os.path.basename(self.tarball)
        return tempfile.mkdtemp(prefix=f"{basename}_meta_")

    def extract_metafile(self):
        raise NotImplementedError


class NpmMeta(MetaBase):
    def __init__(self, source_tarball):
        self.metafile = "package.json"
        super().__init__(source_tarball)

    def get_metadata(self, filepath):
        """
        Accept the package json filepath, returns an NpmPackage.
        """
        # only one `NpmPackage` instance returned from the generator
        packages = parse(filepath)
        return next(packages)

    def extract_metafile(self):
        temp_dir = self._create_temp_meta_dir()
        # the default npm package archive is .tgz
        found = False
        with tarfile.open(self.tarball, "r:gz") as tf:
            for member in tf.getmembers():
                if member.name.endswith(self.metafile):
                    found = True
                    tf.extract(member, temp_dir)
                    break
        return temp_dir if found else None

    def parse_metadata(self):
        try:
            package_json_dir = self.extract_metafile()
            if package_json_dir is not None:
                package_json_filepath = os.path.join(
                    package_json_dir, f"package/{self.metafile}"
                )
                return self.get_metadata(package_json_filepath)
            else:
                return None
        finally:
            if package_json_dir is not None:
                shutil.rmtree(package_json_dir)


class GolangMeta(MetaBase):
    def __init__(self, source_tarball):
        self.metafile = "go.mod"
        super().__init__(source_tarball)

    def extract_metafile(self):
        temp_dir = self._create_temp_meta_dir()
        # the default npm package archive is .tgz
        found = False
        with zipfile.ZipFile(self.tarball) as zf:
            for name in zf.namelist():
                if name.endswith(self.metafile):
                    found = True
                    zf.extract(name, temp_dir)
                    break
        return temp_dir if found else None

    def get_metafile_path(self, meta_dir):
        for path in glob.glob(
            f"{meta_dir}/**/{self.metafile}", recursive=True
        ):
            return path

    def parse_metadata(self):
        try:
            meta_dir = self.extract_metafile()
            if meta_dir is not None:
                meta_filepath = self.get_metafile_path(meta_dir)
                packages = GolangPackage.recognize(meta_filepath)
                return next(packages)
            else:
                return None
        finally:
            if meta_dir is not None:
                shutil.rmtree(meta_dir)
