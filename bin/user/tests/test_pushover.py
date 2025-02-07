# pylint: disable=wrong-import-order
# pylint: disable=missing-docstring
# pylint: disable=invalid-name

import unittest
import mock

import configobj
import random
import string
import time

from user.pushover import Pushover

def random_string(length=32):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)]) # pylint: disable=unused-variable

class TestObservationMissing(unittest.TestCase):
    def setup_config_dict(self,
                          binding,
                          observation,
                          label=None,
                          name=None,
                          count=10,
                          wait_time=3600):
        config_dict = {
            'Pushover':
            {
                binding:
                {
                    observation:
                    {
                        'missing':
                        {
                            'count': count,
                            'wait_time': wait_time,
                        }
                    }
                }
            }
        }

        if label:
            config_dict['Pushover'][binding][observation]['label'] = label
        if name:
            config_dict['Pushover'][binding][observation]['weewx_name'] = name

        return config_dict

    def test_at_startup(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        name = observation
        config_dict = self.setup_config_dict('archive', observation, label)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        with mock.patch('user.pushover.log') as mock_logger:
            mock_logger.debug = lambda msg, *args: print("DEBUG: " + msg %args)
            mock_logger.info = lambda msg, *args: print("INFO:  " + msg %args)
            mock_logger.error = lambda msg, *args: print("ERROR: " + msg %args)

            msg = SUT.check_missing_value(observation,
                                          SUT.archive_observations[observation]['name'],
                                          SUT.archive_observations[observation]['label'],
                                          SUT.archive_observations[observation]['missing'])

        self.assertEqual(msg, f"{name} ({label}) is missing with a count of 1.\n")
        self.assertIn(observation, SUT.missing_observations)
        self.assertIn('missing_time', SUT.missing_observations[observation])

    def test_past_time_threshold_past_count_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        name = observation
        count = 10 # To do make random int
        config_dict = self.setup_config_dict('archive', observation, label, count=count)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        with mock.patch('user.pushover.log') as mock_logger:
            mock_logger.debug = lambda msg, *args: print("DEBUG: " + msg %args)
            mock_logger.info = lambda msg, *args: print("INFO:  " + msg %args)
            mock_logger.error = lambda msg, *args: print("ERROR: " + msg %args)

            # Missing notification has been 'sent'.
            # Setting to 1, ensures that time threshold has been met.
            SUT.archive_observations[observation]['missing']['last_sent_timestamp'] = 1
            # Setting to ensure that count threshold has been met.
            SUT.archive_observations[observation]['missing']['counter'] = count - 1

            msg = SUT.check_missing_value(observation,
                                          SUT.archive_observations[observation]['name'],
                                          SUT.archive_observations[observation]['label'],
                                          SUT.archive_observations[observation]['missing'])

            self.assertEqual(msg, f"{name} ({label}) is missing with a count of {count}.\n")
            self.assertIn(observation, SUT.missing_observations)
            self.assertIn('missing_time', SUT.missing_observations[observation])

    def test_past_time_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        count = 10 # To do make random int
        config_dict = self.setup_config_dict('archive', observation, label, count=count)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        with mock.patch('user.pushover.log') as mock_logger:
            mock_logger.debug = lambda msg, *args: print("DEBUG: " + msg %args)
            mock_logger.info = lambda msg, *args: print("INFO:  " + msg %args)
            mock_logger.error = lambda msg, *args: print("ERROR: " + msg %args)

            # Missing notification has been 'sent'.
            # Setting to 1, ensures that time threshold has been met.
            SUT.archive_observations[observation]['missing']['last_sent_timestamp'] = 1
            # Setting to ensure that count threshold has NOT been met.
            SUT.archive_observations[observation]['missing']['counter'] = 0

            msg = SUT.check_missing_value(observation,
                                          SUT.archive_observations[observation]['name'],
                                          SUT.archive_observations[observation]['label'],
                                          SUT.archive_observations[observation]['missing'])

            self.assertEqual(msg, "")
            self.assertIn(observation, SUT.missing_observations)

    def test_past_count_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        count = 10 # To do make random int
        config_dict = self.setup_config_dict('archive', observation, label, count=count)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        with mock.patch('user.pushover.log') as mock_logger:
            mock_logger.debug = lambda msg, *args: print("DEBUG: " + msg %args)
            mock_logger.info = lambda msg, *args: print("INFO:  " + msg %args)
            mock_logger.error = lambda msg, *args: print("ERROR: " + msg %args)

            # Missing notification has been 'sent'.
            # Setting to 1, ensures that time threshold has NOT been met.
            SUT.archive_observations[observation]['missing']['last_sent_timestamp'] = time.time()
            # Setting to ensure that count threshold has been met.
            SUT.archive_observations[observation]['missing']['counter'] = count - 1

            msg = SUT.check_missing_value(observation,
                                          SUT.archive_observations[observation]['name'],
                                          SUT.archive_observations[observation]['label'],
                                          SUT.archive_observations[observation]['missing'])

            self.assertEqual(msg, "")
            self.assertIn(observation, SUT.missing_observations)

if __name__ == '__main__':
    #test_suite = unittest.TestSuite()
    #test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    #unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
