# pylint: disable=wrong-import-order
# pylint: disable=missing-docstring

import unittest
import mock

import configobj
import io

from user.pushover import Pushover

CONFIG_DICT = \
"""
"""

class Tests(unittest.TestCase):
    def tests_one(self):
        print("one")
        mock_engine = mock.Mock()
        config = configobj.ConfigObj(io.StringIO(CONFIG_DICT))
        SUT = Pushover(mock_engine, config)

        print("done")

if __name__ == '__main__':
    print("start")

    test_suite = unittest.TestSuite()
    test_suite.addTest(Tests('tests_one'))
    #test_suite.addTest(Tests('tests_two'))
    unittest.TextTestRunner().run(test_suite)

    #unittest.main(exit=False)

    print("done")
