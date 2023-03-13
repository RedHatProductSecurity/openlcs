class OpenLCSException(Exception):
    pass


class MissingBinaryBuildException(OpenLCSException):
    """
    Exception to capture where corgi's OCI source build "-source" missing
    binary build.

    See also OLCS-459
    """
    pass
