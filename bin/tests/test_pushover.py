# pylint: disable=wrong-import-order
# pylint: disable=missing-docstring
# pylint: disable=invalid-name

import unittest
import mock

import configobj
import io
import random
import string

from user.pushover import Pushover

def random_string(length=32):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)]) # pylint: disable=unused-variable
observation = random_string()
label = random_string()

CONFIG_DICT = \
f"""
[Pushover]
    [[archive]]
        [[[{observation}]]]
           label = {label}
           [[[[missing]]]]
               wait_time = 7200
"""

class TestObservationMissing(unittest.TestCase):
    def tests_observation_missing_at_startup(self):
        print("one")
        mock_engine = mock.Mock()
        config = configobj.ConfigObj(io.StringIO(CONFIG_DICT))

        SUT = Pushover(mock_engine, config)

        with mock.patch('user.pushover.log') as mock_logger:
            mock_logger.debug = lambda msg, *args: print("DEBUG: " + msg %args)
            mock_logger.info = lambda msg, *args: print("INFO:  " + msg %args)
            mock_logger.error = lambda msg, *args: print("ERROR: " + msg %args)

            msg = SUT.check_missing_value(observation,
                                          SUT.archive_observations[observation]['name'],
                                          SUT.archive_observations[observation]['label'],
                                          SUT.archive_observations[observation]['missing'])
        print(msg)

        print("done")

if __name__ == '__main__':
    print("start")

    test_suite = unittest.TestSuite()
    test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    unittest.TextTestRunner().run(test_suite)

    #unittest.main(exit=False)

    print("done")
