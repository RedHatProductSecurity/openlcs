from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.core.validators import URLValidator
# avoid name clash
import uuid as uuid_module


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

    def __str__(self):
        return f'{self.source}, {self.path}'


class CorgiComponentMixin(models.Model):
    """Model mixin for corgi component attributes

    Fields here are synced from corgi, and should not be overwritten.
    If more corgi readonly fields are needed in future, put it here.
    """

    # uuid uniquely identifies a corgi component.
    uuid = models.UUIDField(
        unique=True,
        help_text='Corgi component uuid',
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

    uuid = models.UUIDField(
        unique=True,
        default=uuid_module.uuid4,
        help_text='Component uuid',
    )
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
    synced = models.BooleanField(
        default=False,
        help_text="Indicate whether the component is synced with component "
                  "from component registry. Synced component should have "
                  "identical uuid.",
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

    def sync_with_corgi(self, data):
        if not self.synced:
            self.uuid = data.get("uuid")
            # FIXME: should we add a validation here? i.e,. is it possible to
            # have inconsistent name/version/release/arch/type while syncing?
            self.synced = True
            self.save()

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
    name = models.CharField(max_length=255)
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

    def __str__(self):
        return f"{self.name}"
