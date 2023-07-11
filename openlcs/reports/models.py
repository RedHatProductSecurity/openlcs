from itertools import islice

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

    @classmethod
    def bulk_create_objects(cls, new_file_ids, detector, batch_size=1000):
        objs = (
            FileLicenseScan(detector=detector,
                            file_id=file_id) for file_id in new_file_ids
        )

        file_license_scan_list = []
        while True:
            batch = list(islice(objs, batch_size))
            if not batch:
                break
            file_license_scan_list.extend(FileLicenseScan.objects.bulk_create(
                batch, batch_size=batch_size))

        return file_license_scan_list

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

    @classmethod
    def bulk_create_objs(cls, new_file_ids, copyright_detector,
                         batch_size=1000):
        objs = (
            FileCopyrightScan(file_id=file_id, detector=copyright_detector)
            for file_id in new_file_ids)
        file_copyright_scan_list = []
        while True:
            batch = list(islice(objs, batch_size))
            if not batch:
                break
            file_copyright_scan_list.extend(
                FileCopyrightScan.objects.bulk_create(
                    batch, batch_size=batch_size)
            )

        return file_copyright_scan_list

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
        constraints = [
            models.UniqueConstraint(
                fields=['license_key', 'score', 'rule', 'start_line',
                        'end_line', 'false_positive', 'file_scan'],
                name='unique_license_detection'
            ),
        ]

    @classmethod
    def bulk_create_objects(cls, licenses, batch_size=1000):
        objs = (
                LicenseDetection(
                    file_scan_id=lic[0],
                    license_key=lic[1],
                    score=lic[2],
                    start_line=lic[3],
                    end_line=lic[4],
                    rule=lic[6],
                ) for lic in licenses
            )
        # existing_objs = LicenseDetection.objects.all()
        # new_objs = [obj for obj in objs if obj not in existing_objs]
        while True:
            batch = list(islice(objs, batch_size))
            if not batch:
                break
            LicenseDetection.objects.bulk_create(
                batch, ignore_conflicts=True, batch_size=batch_size)

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

    @classmethod
    def bulk_create_objs(cls,  copyrights):
        # Query copyrights detection that need to be created.
        objs = []
        for k, v in copyrights.items():
            k_objs = [
                CopyrightDetection(
                    file_scan_id=k,
                    statement=statement["copyright"],
                    start_line=statement["start_line"],
                    end_line=statement["end_line"]
                ) for statement in v
            ]
            objs.extend(k_objs)
        # existing_objs = CopyrightDetection.objects.all()
        # new_objs = [obj for obj in objs if obj not in existing_objs]
        CopyrightDetection.objects.bulk_create(
            objs, ignore_conflicts=True, batch_size=1000)

    class Meta:
        app_label = 'reports'
        constraints = [
            models.UniqueConstraint(
                fields=['statement', 'false_positive', 'start_line',
                        'end_line', 'file_scan'],
                name='unique_copyright_detection'
            ),
        ]

    def __str__(self):
        return f'{self.file_scan}, {self.statement}'
