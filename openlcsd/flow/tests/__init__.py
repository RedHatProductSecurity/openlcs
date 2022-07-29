import unittest
from openlcsd.flow.tests.test_deduplicate_source import TestDeduplicateSource
from openlcsd.flow.tests.test_repack_source import TestRepackSource

suite = unittest.TestSuite()
# Add all flow test modules here
suite.addTest(unittest.makeSuite(TestDeduplicateSource))
suite.addTest(unittest.makeSuite(TestRepackSource))

runner = unittest.TextTestRunner()
runner.run(suite)
