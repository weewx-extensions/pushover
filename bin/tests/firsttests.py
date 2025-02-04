# pylint: disable=wrong-import-order
# pylint: disable=missing-docstring
# pylint: disable=invalid-name

import unittest
import mock

import configobj
import io

from user.pushover import Pushover

CONFIG_DICT = \
"""
"""

class TestObservationMissing(unittest.TestCase):
    def tests_observation_missing_at_startup(self):
        print("one")
        mock_engine = mock.Mock()
        config = configobj.ConfigObj(io.StringIO(CONFIG_DICT))

        observation_detail = {'last_sent_timestamp': 0,
                              'wait_time': 0,
                              'counter': 0,
                              'count': 0,}

        SUT = Pushover(mock_engine, config)
        msg = SUT.check_missing_value('outTemp8',
                                      'outTemp8',
                                      'label for outTemp8',
                                      observation_detail)
        print(msg)

        print("done")

if __name__ == '__main__':
    print("start")

    test_suite = unittest.TestSuite()
    test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    unittest.TextTestRunner().run(test_suite)

    #unittest.main(exit=False)

    print("done")
