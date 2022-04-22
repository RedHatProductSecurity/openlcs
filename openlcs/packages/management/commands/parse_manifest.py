from django.core.management.base import BaseCommand
from libs.parsers import parse_manifest_file


class Command(BaseCommand):
    help = 'Parser for the product/package manifest file'

    def add_arguments(self, parser):
        parser.add_argument(
            'manifest_filepath',
            help='Product/package manifest file path in json format.',
        )

    def handle(self, *args, **options):
        manifest_filepath = options['manifest_filepath']
        try:
            data = parse_manifest_file(manifest_filepath)
        except RuntimeError as e:
            raise RuntimeError(f'RuntimeError: {e.args[0]}') from e
        else:
            # FIXME: 'components' are available in data['src_packages'] and
            # data['containers'], trigger package/container import task here
            # once it's ready.
            print(
                f"Successfully parsed {data['productname']}-{data['version']}!"
            )
