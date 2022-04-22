import unittest
from openlcsd.flow.tests.test_deduplicate_source import TestDeduplicateSource
from openlcsd.flow.tests.test_repack_source import TestRepackSource
from openlcsd.flow.tests.test_upload_archive_to_deposit import TestUploadArchiveToDeposit  # noqa

suite = unittest.TestSuite()
# Add all flow test modules here
suite.addTest(unittest.makeSuite(TestDeduplicateSource))
suite.addTest(unittest.makeSuite(TestRepackSource))
suite.addTest(unittest.makeSuite(TestUploadArchiveToDeposit))

runner = unittest.TextTestRunner()
runner.run(suite)
