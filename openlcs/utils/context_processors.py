from pathlib import Path


def get_version():
    version_file = Path(__file__).resolve().parent.parent / 'VERSION.txt'
    try:
        with version_file.open() as file:
            version = file.read().strip()
    except FileNotFoundError:
        version = 'Unknown'
    return version


def get_app_version(request):
    # FIXME: hub/worker may have their own version bumps later, in that case,
    # we may need to tweak the `get_version` to have different hub/worker
    # versions
    return {"app_version": get_version()}
