from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class PelcStaticFilesStorage(ManifestStaticFilesStorage):
    """
    Django's ManifestStaticFilesStorage provides versioning for assets via
    adding hashes to the filename, so that we can use far-future expires
    headers and not worry about serving old versions of files.

    By default it activates the hashing when DEBUG is False, but since we use
    DEBUG for all non-production environments we would still get problems with
    stale assets during testing. The reason is that hashing only works after
    collectstatic has been run, which is typically not done in local
    deployments or when running tests.

    This class modifies it to also (in addition to DEBUG being False) activate
    when the asset index file is available, which will be true for deployed
    environments, but typically not for local deployment.
    """
    def url(self, name, force=False):
        force = force or bool(self.hashed_files)
        return super(PelcStaticFilesStorage, self).url(name, force=force)
