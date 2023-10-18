from django.db import models
from django.db.models import Q
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.core.validators import URLValidator
# avoid name clash
import uuid as uuid_module

from libs.corgi import CorgiConnector


# Create your models here.
class File(models.Model):
    """
    files are used to store the information of swh uuid.
    """
    swhid = models.CharField(
        max_length=50,
        verbose_name="SWH ID",
        help_text='SoftWare Heritage persistent IDentifier',
        unique=True
    )

    class Meta:
        app_label = 'packages'

    def __str__(self):
        return self.swhid


class Source(models.Model):
    """
    Sources for source package information.
    """
    checksum = models.CharField(
        max_length=64,
        unique=True,
        help_text='Checksum for this package'
    )
    name = models.CharField(
        max_length=128,
        help_text='Name of this package'
    )
    url = models.TextField(
        blank=True, null=True,
        verbose_name="URL",
        validators=[URLValidator(message='Please enter a valid URL.')],
        help_text='Upstream project URL'
    )
    state = models.IntegerField(
        default=0,
        help_text='Used to track package analysis status'
    )
    archive_type = models.CharField(
        max_length=8,
        help_text='Type of archive'
    )
    scan_flag = models.TextField(
        null=True, blank=True,
        help_text='A comma separated "scan_type(detector)"'
    )

    class Meta:
        app_label = 'packages'

    def __str__(self):
        return self.checksum

    def get_license_scans(self, detector=None):
        from reports.models import FileLicenseScan
        file_ids = self.file_paths.values_list('file__pk', flat=True)
        filters = [Q(file__in=file_ids)]
        if detector:
            filters.append(Q(detector=detector))
        return FileLicenseScan.objects.filter(*filters)

    def get_license_detections(self):
        from reports.models import LicenseDetection
        license_scans = self.get_license_scans()
        return LicenseDetection.objects.filter(
                file_scan__in=license_scans, false_positive=False)

    def get_copyright_scans(self, detector=None):
        from reports.models import FileCopyrightScan
        file_ids = self.file_paths.values_list('file__pk', flat=True)
        filters = [Q(file__in=file_ids)]
        if detector:
            filters.append(Q(detector=detector))
        return FileCopyrightScan.objects.filter(*filters)

    def get_copyright_detections(self):
        from reports.models import CopyrightDetection
        copyright_scans = self.get_copyright_scans()
        return CopyrightDetection.objects.filter(
                file_scan__in=copyright_scans, false_positive=False)


class Path(models.Model):
    """
    Path for files and sources.
    """
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name="file_paths",
        help_text='Reference to source package'
    )
    file = models.ForeignKey(
        File,
        on_delete=models.RESTRICT,
        help_text='Reference to a file'
    )
    path = models.TextField(
        help_text='File path within source package'
    )

    class Meta:
        app_label = 'packages'
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'path'],
                name='unique_source_path'
            ),
        ]

    @classmethod
    def bulk_create_objects(cls, source, paths,
                            batch_size=settings.BULK_CREATE_BATCH_SIZE):
        file_ids = [p.get('file') for p in paths]
        files = File.objects.filter(swhid__in=file_ids).values('swhid', 'id')
        file_mapping = {file['swhid']: file['id'] for file in files}
        path_objs = [
            Path(source=source,
                 file_id=file_mapping[p.get('file')],
                 path=p.get('path')) for p in paths
        ]

        Path.objects.bulk_create(path_objs, batch_size=batch_size)

    def __str__(self):
        return f'{self.source}, {self.path}'


class CorgiComponentMixin(models.Model):
    """Model mixin for corgi component attributes

    Fields here are synced from corgi, and should not be overwritten.
    If more corgi readonly fields are needed in the future, put it here.
    """

    # Specify explicitly the `uuid` field if data is from corgi.
    uuid = models.UUIDField(
        unique=True,
        default=uuid_module.uuid4,
        help_text='Component uuid',
    )
    type = models.CharField(
        max_length=50,
        help_text='Corgi component type',
    )
    name = models.TextField()
    version = models.CharField(max_length=1024)
    release = models.CharField(max_length=1024, default="")
    arch = models.CharField(max_length=1024, default="")
    purl = models.CharField(
        max_length=1024,
        blank=True,
        default="",
        help_text='Corgi component purl',
    )

    class Meta:
        abstract = True


class Component(CorgiComponentMixin):

    # inspired from https://docs.djangoproject.com/en/3.2/ref/models/
    # fields/#enumeration-types
    class SyncStatus(models.TextChoices):
        SYNCED = 'synced', 'Synced'
        UNSYNCED = 'unsynced', 'Unsynced'
        SYNC_FAILED = 'sync_failed', 'Sync Failed'

    class SyncFailureReason(models.TextChoices):
        # Add all possible failures
        REQUEST_TIMEOUT = 'request_timeout', 'Request timeout'
        SCAN_EXCEPTION = 'scan_exception', 'Scan exception'
        MISSING_DOWNLOAD_URL = 'missing_download_url', 'Missing download url'
        UNKNOWN_FAILURE = 'unknown_failure', 'Unknown failure'

    source = models.ForeignKey(
        Source,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Reference to component source'
    )
    # Note: license field is also available in corgi, value should be
    # populated from there if possible. If corgi license is empty,
    # OpenLCS scans/populate it and possibly pushes back to corgi.
    summary_license = models.TextField(
        blank=True,
        default='',
        help_text='Declared summary license expression'
    )
    # FIXME: migrated from existing "models.Package". This is probably
    #  no longer needed since we already have "arch"
    is_source = models.BooleanField(
        default=False,
        help_text="True if this component corresponds to the entire "
                  "source, rather than an actual binary package",
    )
    from_corgi = models.BooleanField(
        default=False,
        help_text='True if created from component registry'
    )
    sync_status = models.CharField(
        max_length=50,
        choices=SyncStatus.choices,
        default=SyncStatus.UNSYNCED
    )
    sync_failure_reason = models.CharField(
        max_length=50,
        choices=SyncFailureReason.choices,
        null=True,
        blank=True,
        default=None
    )
    component_nodes = GenericRelation(
        "products.ComponentTreeNode", related_query_name="component"
    )
    release_nodes = GenericRelation(
        "products.ProductTreeNode", related_query_name="component"
    )

    class Meta:
        # Ensure constraints to be consistent with corgi component
        constraints = [
            models.UniqueConstraint(
                name="unique_components",
                fields=("name", "version", "release", "arch", "type"),
            ),
        ]

    @classmethod
    def update_or_create_component(cls, component_data):
        """
        Get or create a component based on the given data.

        Param `component_data` is a dictionary of (nested) component data.
        We need to tell whether the component_data is from component registry
        or not. My decision is to check key existence of `uuid`, if `uuid`
        is in, it will be data from component registry.
        """
        # Keep this consistent with `self.Meta.constraints`.
        unique_fields = ['name', 'version', 'release', 'arch', 'type']
        # Explicitly specify below default fields. Other fields
        # (`sync_status`` etc) should be manipulated elsewhere.
        defaults = {
            # data from corgi contains `uuid`, let's persist if applicable.
            # there are chances when an existing component(not from corgi)
            # instance shares identical `nvrat` with corgi component data,
            # in this case, we make sure `uuid`, `from_corgi` fields are
            # updated accordingly.
            'uuid': component_data.get('uuid', uuid_module.uuid4()),
            'from_corgi': True if 'uuid' in component_data else False,
            'purl': component_data.get('purl', ''),

            "summary_license": "" if component_data.get('summary_license') \
            is None else component_data['summary_license']
        }

        if "is_source" in component_data:
            defaults['is_source'] = component_data["is_source"]

        component, _ = cls.objects.update_or_create(
            **{f: component_data.get(f, '') for f in unique_fields},
            defaults=defaults,
        )
        return component

    @property
    def sync_needed(self):
        return self.from_corgi and self.sync_status != self.SyncStatus.SYNCED

    def sync_with_corgi(self, data):
        if self.sync_needed:
            self.uuid = data.get("uuid")
            # FIXME: should we add a validation here? i.e,. is it possible to
            # have inconsistent name/version/release/arch/type while syncing?
            self.sync_status = True
            self.save()

    def save(self, *args, **kwargs):
        # only failed sync has a reason
        if self.sync_status != self.SyncStatus.SYNC_FAILED:
            self.sync_failure_reason = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name}-{self.version}, {self.type}'


class ComponentSubscriptionManager(models.Manager):

    def get_active_subscriptions(self):
        return self.filter(active=True)


class ComponentSubscription(models.Model):
    """
    Subscription model controls which components in component registry
    should be processed.
    """
    name = models.CharField(unique=True, max_length=255)
    # various query params being used in corgi's `/components` api endpoint
    query_params = models.JSONField()
    # component purls are populated/updated in the periodical tasks.
    # the number of components may vary over time.
    # a previous sync guarantees all components were processed, all subsequent
    # sync maintain the latest fetched components from corgi, and focuses
    # only on the newly added components.
    component_purls = ArrayField(
        models.CharField(max_length=1024),
        default=list,
        blank=True,
        null=True,
    )
    source_purls = ArrayField(
        models.CharField(max_length=1024),
        default=list,
        blank=True,
        null=True,
    )

    # a subscription may be no loner valid over time. set it to False to
    # prevent it from being taken by the sync task.
    active = models.BooleanField(default=True)
    # move this to a separate mixin model if timestamp is needed elsewhere.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ComponentSubscriptionManager()

    def deactivate(self):
        self.active = False
        self.save()

    def get_latest_component_purls(self):
        purls = []
        connector = CorgiConnector()
        try:
            for component in connector.get_paginated_data(self.query_params):
                purls.append(component.get("purl"))
        except Exception:
            pass
        return purls

    def populate_component_purls(self):
        purls = self.get_latest_component_purls()
        self.component_purls = purls
        self.save()

    def get_delta_component_purls(self, purls):
        """
        Compute the `delta` components as compared with previous sync.
        Used to de-duplicate components that were previously processed.

        e.g., suppose after a previosly sync, we have
        `self.component_purls = ["purl1", "purl2", "purl3"]`
        and the latest sync yields
        `purls = ["purl2", "purl3", "purl4", "purl5"],

        this function returns ["purl4", "purl5"] which should be processed,
        others were processed earlier.
        """
        return filter(lambda p: p not in self.component_purls, purls)

    def update_component_purls(self, component_purls, update_mode="append"):
        purls_set = set(component_purls)
        merged_purls_set = purls_set.union(set(self.component_purls))
        purls = list(merged_purls_set)

        if update_mode == "append":
            self.component_purls = purls
        else:
            self.component_purls = list(purls_set)
        self.save()

    def update_source_purls(self, source_purls, update_mode="append"):
        purls_set = set(source_purls)
        merged_purls_set = purls_set.union(set(self.source_purls))
        purls = list(merged_purls_set)

        if update_mode == "append":
            self.source_purls = purls
        else:
            self.source_purls = list(purls_set)
        self.save()

    def get_synced_components(self):
        return Component.objects.filter(
                purl__in=self.source_purls, sync_status='synced')

    def __str__(self):
        return f"{self.name}"


class MissingComponent(models.Model):
    purl = models.CharField(
        max_length=1024,
        unique=True,
        help_text='Corgi component purl',
    )
    subscriptions = models.ManyToManyField(
        ComponentSubscription,
        related_name="missing_components"
    )

    def __str__(self):
        return f"{self.purl}"
