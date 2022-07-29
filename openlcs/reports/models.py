from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from packages.models import File


class FileLicenseScan(models.Model):
    file = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        related_name="license_scans",
        help_text='Reference to a file'
    )
    detector = models.CharField(
        max_length=32,
        help_text='License detector with version detail'
    )

    class Meta:
        app_label = 'reports'
        constraints = [
            models.UniqueConstraint(
                fields=['file', 'detector'],
                name='unique_file_license_scan'
            ),
        ]

    def __str__(self):
        return f'{self.file}, {self.detector}'


class FileCopyrightScan(models.Model):
    file = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        related_name="copyright_scans",
        help_text='Reference to a file'
    )
    detector = models.CharField(
        max_length=32,
        help_text='Copyright detector with version detail'
    )

    class Meta:
        app_label = 'reports'
        constraints = [
            models.UniqueConstraint(
                fields=['file', 'detector'],
                name='unique_file_copyright_scan'
            ),
        ]

    def __str__(self):
        return f'{self.file}, {self.detector}'


class LicenseDetection(models.Model):
    # This should be a reference to licenses table in the future.
    license_key = models.CharField(
        max_length=128,
        verbose_name='license identifier'
    )
    score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='License match score (0 - 100)'
    )
    rule = models.TextField(
        null=True, blank=True,
        help_text='How the license is detected'
    )
    start_line = models.IntegerField(
        null=True, blank=True,
        help_text='Beginning of license match'
    )
    end_line = models.IntegerField(
        null=True, blank=True,
        help_text='End of license match'
    )
    false_positive = models.BooleanField(
        default=False,
        help_text='True if this detection is a false positive'
    )
    file_scan = models.ForeignKey(
        FileLicenseScan,
        on_delete=models.CASCADE,
        related_name="license_detections",
        help_text='Reference to a file license scan'
    )

    class Meta:
        app_label = 'reports'

    def __str__(self):
        return f'{self.file_scan}, {self.license_key}'


class CopyrightDetection(models.Model):
    statement = models.TextField(
        help_text='Copyright statement'
    )
    false_positive = models.BooleanField(
        default=False,
        help_text='True if this detection is a false positive'
    )
    start_line = models.IntegerField(
        null=True, blank=True,
        help_text='Beginning of copyright match'
    )
    end_line = models.IntegerField(
        null=True, blank=True,
        help_text='End of copyright match'
    )
    file_scan = models.ForeignKey(
        FileCopyrightScan,
        on_delete=models.CASCADE,
        related_name="copyright_detections",
        help_text='Reference to a file copyright scan'
    )

    class Meta:
        app_label = 'reports'

    def __str__(self):
        return f'{self.file_scan}, {self.statement}'
