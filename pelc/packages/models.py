from django.db import models
from django.core.validators import URLValidator


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

    class Meta:
        app_label = 'packages'

    def __str__(self):
        return self.checksum


class Path(models.Model):
    """
    Path for files and sources.
    """
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
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


class Package(models.Model):
    """
    Source files for a given archive.
    """
    nvr = models.CharField(
        max_length=512,
        verbose_name='NVR',
        help_text='Package nvr'
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        help_text='Reference to source package'
    )
    sum_license = models.TextField(
        null=True, blank=True,
        help_text='Package declared summary license expression'
    )
    is_source = models.BooleanField(
        default=False,
        help_text='True if this package corresponds to the entire source, rather than an actual binary package' # noqa
    )

    class Meta:
        app_label = 'packages'
        constraints = [
            models.UniqueConstraint(
                fields=['nvr', 'source'],
                name='unique_nvr_source'
            ),
        ]

    def __str__(self):
        return f'{self.nvr}, {self.source}'
