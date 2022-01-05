from swh.model.cli import swhid_of_file
from swh.model.swhids import SWHID_RE


def swhid_check(swhid):
    """
    SWHID　validity check.

    Copy the code from link:
    https://github.com/SoftwareHeritage/swh-model/blob/94b00d6877aff003ea060aa6110300ee37c3b295/swh/model/swhids.py#L441  # noqa
    """
    m = SWHID_RE.fullmatch(swhid)
    if not m:
        raise ValueError(f'Invalid SWHID: invalid syntax: {swhid}')
    return swhid


def get_swhids(paths):
    """
    Get SWH IDs of package source file paths.
    """
    return [swhid_of_file(path) for path in paths]
