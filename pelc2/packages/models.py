from django.db import models


# Create your models here.
class File(models.Model):
    """
    files are used to store the information of swh uuid.
    """
    swhid = models.CharField(
        max_length=50,
        verbose_name="SWH ID",
        help_text='SoftWare Heritage persistent IDentifier'
    )

    class Meta:
        app_label = 'packages'

    def __str__(self):
        return self.swhid
