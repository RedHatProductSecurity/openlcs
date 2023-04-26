class OpenLCSException(Exception):
    pass  # pylint: disable=unnecessary-pass


class MissingBinaryBuildException(OpenLCSException):
    """
    Exception to capture where corgi's OCI source build "-source" missing
    binary build.

    See also OLCS-459
    """
    pass  # pylint: disable=unnecessary-pass


class UnsupportedPriority(OpenLCSException):
    pass  # pylint: disable=unnecessary-pass
