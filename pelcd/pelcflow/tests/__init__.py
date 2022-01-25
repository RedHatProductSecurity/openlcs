import unittest
from pelcd.pelcflow.tests.test_deduplicate_source import TestDeduplicateSource
from pelcd.pelcflow.tests.test_repack_source import TestRepackSource
from pelcd.pelcflow.tests.test_upload_archive_to_deposit import TestUploadArchiveToDeposit  # noqa

suite = unittest.TestSuite()
# Add all pelcflow test modules here
suite.addTest(unittest.makeSuite(TestDeduplicateSource))
suite.addTest(unittest.makeSuite(TestRepackSource))
suite.addTest(unittest.makeSuite(TestUploadArchiveToDeposit))

runner = unittest.TextTestRunner()
runner.run(suite)
