import os
import shutil


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
