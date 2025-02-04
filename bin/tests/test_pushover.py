# pylint: disable=wrong-import-order
# pylint: disable=missing-docstring
# pylint: disable=invalid-name

import unittest
import mock

import configobj
import random
import string

from user.pushover import Pushover

def random_string(length=32):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)]) # pylint: disable=unused-variable

class TestObservationMissing(unittest.TestCase):
    def setup_config_dict(self, binding, observation, label=None, name=None):
        config_dict = {
            'Pushover':
            {
                binding:
                {
                    observation:
                    {
                        'missing':
                        {
                            'wait_time': 7200
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

    def tests_observation_missing_at_startup(self):
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

        self.assertEqual(msg, f"{name} ({label}) is missing.\n")
        self.assertIn(observation, SUT.missing_observations)
        self.assertIn('missing_time', SUT.missing_observations[observation])

if __name__ == '__main__':
    #test_suite = unittest.TestSuite()
    #test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    #unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
