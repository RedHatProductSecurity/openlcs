from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from packages.models import File


class LicenseDetection(models.Model):
    file = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        help_text='Reference to a file'
    )
    # This should be a reference to licenses table in future.
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
    detector = models.CharField(
        max_length=32,
        help_text='License detector with version detail'
    )

    class Meta:
        app_label = 'reports'

    def __str__(self):
        return '%s, %s, %s' % (
                self.file, self.license_key, self.detector)


class CopyrightDetection(models.Model):
    file = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        help_text='Reference to a file'
    )
    statement = models.TextField(
        null=True, blank=True,
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
    detector = models.CharField(
        max_length=32,
        help_text='Copyright detector with version detail'
    )

    class Meta:
        app_label = 'reports'

    def __str__(self):
        return '%s, %s' % (self.file, self.detector)
