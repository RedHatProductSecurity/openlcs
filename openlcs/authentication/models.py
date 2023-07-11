import uuid as uuid

from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

User = get_user_model()


class RedHatProfile(models.Model):
    """
    Additional information provided by Red Hat SSO, used for access controls
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE
    )
    sub = models.UUIDField(default=uuid.uuid4)
    # Storing CN instead of trying to split it into Django's given/first/family/last  # noqa
    # bc https://www.kalzumeus.com/2010/06/17/falsehoods-programmers-believe-about-names/  # noqa
    full_name = models.CharField(max_length=256, blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} <{self.user.email}>"


def user_post_save(sender, instance, created, **kwargs):
    """Create a user profile when a new user account is created"""
    if created:
        rhat_profile = RedHatProfile(user=instance)
        rhat_profile.save()


post_save.connect(user_post_save, sender=User)
