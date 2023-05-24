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


class TaskResubmissionException(OpenLCSException):
    """Raised when tasks with identical name/args are submitted
    simultaneously.

    This is enforced by acquiring a dedicated lock for each submitted task,
    lock won't be released unless tasks are finished, meaning no more tasks
    with identical name/args are allowed to be submitted again.
    """
    pass  # pylint: disable=unnecessary-pass
