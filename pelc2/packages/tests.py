from django.test import TestCase
from packages.models import File


# Create your tests here.
class FileModelTest(TestCase):
    def setUp(self):
        super(FileModelTest, self).setUp()
        self.swhid = "123-456-789"
        File.objects.create(swhid=self.swhid)

    def test_file_model(self):
        file = File.objects.get(id=1)
        self.assertEqual(
            file.swhid, self.swhid,
            f'Cannot get the correct swhid {self.swhid}'
        )

        file_count = File.objects.filter(swhid=self.swhid).count()
        self.assertEqual(
            file_count, 1,
            f'Should only exist 1 record with swhid {self.swhid}'
        )
