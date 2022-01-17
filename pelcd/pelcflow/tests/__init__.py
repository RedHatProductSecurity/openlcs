import unittest
from pelcd.pelcflow.tests.test_deduplicate_source import TestDeduplicateSource
# from pelcd.pelcflow.tests.test_repack_package import TestRepackPackage
# from pelcd.pelcflow.tests.test_upload_to_eposit import TestUploadToDeposit

suite = unittest.TestSuite()
# Add all pelcflow test modules here
suite.addTest(unittest.makeSuite(TestDeduplicateSource))
# suite.addTest(unittest.makeSuite(TestRepackPackage))
# suite.addTest(unittest.makeSuite(TestUploadToDeposit))

runner = unittest.TextTestRunner()
runner.run(suite)
