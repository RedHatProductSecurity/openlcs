from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

User = get_user_model()


class Profile(models.Model):
    """
    Model to represent additional information about users, we don't have to
    save this info into OpenLCS at present, however, preserve it in case we
    need such information.
    """
    user = models.OneToOneField(User, primary_key=True,
                                on_delete=models.CASCADE)
    realname = models.TextField(blank=True, null=True)
    manager = models.ForeignKey(
        User,
        related_name="staffs",
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )

    def __unicode__(self):
        return "%s's profile" % self.user


def user_post_save(sender, instance, created, **kwargs):
    """Create a user profile when a new user account is created"""
    if created:
        profile = Profile(user=instance)
        profile.save()


post_save.connect(user_post_save, sender=User)
