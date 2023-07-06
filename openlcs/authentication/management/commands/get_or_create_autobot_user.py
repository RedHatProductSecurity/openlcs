import os
from django.conf import settings
from django.core.management.base import BaseCommand
from authentication.mixins import GetAutobotTokenMixin
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Get or create the autobot user for integration test'

    @staticmethod
    def export_autobot_token(key):
        token_file = os.path.join(settings.SRC_ROOT_DIR, 'autobot_token_file')
        with open(token_file, 'w', encoding='utf-8') as token_file:
            token_file.write(key)

    def handle(self, *args, **options):
        verbosity = options['verbosity']

        autobot_token_mixin = GetAutobotTokenMixin()
        access_token = autobot_token_mixin.get_access_token()
        user = autobot_token_mixin.get_or_create_user(access_token)
        token, created = Token.objects.get_or_create(user=user)

        self.export_autobot_token(token.key)

        if verbosity >= 1:
            if created:
                msg = 'Created Autobot token.'
            else:
                msg = 'Got autobot token.'
            self.stdout.write(msg)
