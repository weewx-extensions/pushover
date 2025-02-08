#
#    Copyright (c) 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=fixme

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
from weeutil.weeutil import timestamp_to_string

def random_string(length=32):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)]) # pylint: disable=unused-variable

def setup_config_dict(binding,
                        observation,
                        check_type,
                        label=None,
                        name=None,
                        count=10,
                        wait_time=3600,
                        value=None):
    config_dict = {
        'Pushover':
        {
            binding:
            {
                observation:
                {
                    check_type:
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
    if value:
        config_dict['Pushover'][binding][observation][check_type]['value'] = value

    return config_dict

class TestObservationMissing(unittest.TestCase):
    def test_at_startup(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        name = observation
        config_dict = setup_config_dict('archive', observation, 'missing', label)
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
        config_dict = setup_config_dict('archive', observation, 'missing', label, count=count)
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
        config_dict = setup_config_dict('archive', observation, 'missing', label, count=count)
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
        config_dict = setup_config_dict('archive', observation, 'missing', label, count=count)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        with mock.patch('user.pushover.log') as mock_logger:
            mock_logger.debug = lambda msg, *args: print("DEBUG: " + msg %args)
            mock_logger.info = lambda msg, *args: print("INFO:  " + msg %args)
            mock_logger.error = lambda msg, *args: print("ERROR: " + msg %args)

            # Missing notification has been 'sent'.
            # Setting to 1, ensures that time threshold has NOT been met.
            SUT.archive_observations[observation]['missing']['last_sent_timestamp'] = int(time.time())
            # Setting to ensure that count threshold has been met.
            SUT.archive_observations[observation]['missing']['counter'] = count - 1

            msg = SUT.check_missing_value(observation,
                                          SUT.archive_observations[observation]['name'],
                                          SUT.archive_observations[observation]['label'],
                                          SUT.archive_observations[observation]['missing'])

            self.assertEqual(msg, "")
            self.assertIn(observation, SUT.missing_observations)

class TestObservationReturned(unittest.TestCase):
    def test_observation_not_missing(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = random_string()
        name = observation
        value = 99.9 # ToDo: make random

        config_dict = setup_config_dict(binding, observation, 'missing', label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        SUT.missing_observations = {}

        msg = SUT.check_value_returned(observation,
                                       name,
                                       label,
                                       SUT.archive_observations[observation]['missing'],
                                       value)

        self.assertEqual(msg, "")

    def test_observation_missing_no_notification(self):
        mock_engine = mock.Mock()
        now = int(time.time())

        binding = 'archive'
        observation = random_string()
        label = random_string()
        name = observation
        value = 99.9 # ToDo: make random

        config_dict = setup_config_dict(binding, observation, 'missing', label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        SUT.missing_observations = {
            observation: {
                'notification_count': 0,
                'missing_time': now,
            }
        }

        msg = SUT.check_value_returned(observation,
                                       name,
                                       label,
                                       SUT.archive_observations[observation]['missing'],
                                       value)

        self.assertEqual(msg, "")

    def test_observation_missing_with_notification(self):
        mock_engine = mock.Mock()
        now = int(time.time())

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99.9 # ToDo: make random

        config_dict = setup_config_dict(binding, observation, 'missing', label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        SUT.missing_observations = {
            observation: {
                'notification_count': 1, # ToDo: randomize, integer greater than 0
                'missing_time': now,
            }
        }

        msg = SUT.check_value_returned(observation,
                                       name,
                                       label,
                                       SUT.archive_observations[observation]['missing'],
                                       value)

        self.assertEqual(msg,
                        (f"{name}{label} missing at {timestamp_to_string(now)} "
                         f"returned after missing for 0 with value {value}.\n"))

class TestObservationEqualCheck(unittest.TestCase):
    def test_observation_equal(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        msg = SUT.check_equal_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      value)

        self.assertEqual(msg, "")

    def test_observation_not_equal_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int
        record_value = 55 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        msg = SUT.check_equal_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      record_value)

        self.assertEqual(msg, "")

    def test_observation_not_equal_with_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int
        record_value = 55 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        SUT.archive_observations[observation]['equal']['counter'] = \
            SUT.archive_observations[observation]['equal']['count'] + 1

        msg = SUT.check_equal_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      record_value)


        self.assertEqual(msg, f"{name}{label} value {record_value} is not equal to {value}.\n")

class TestObservationMaxCheck(unittest.TestCase):
    def test_observation_not_greater(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        msg = SUT.check_max_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      value)

        self.assertEqual(msg, "")

    def test_observation_greater_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int
        record_value = 155 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        msg = SUT.check_max_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      record_value)

        self.assertEqual(msg, "")

    def test_observation_greater_with_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int
        record_value = 155 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        SUT.archive_observations[observation]['equal']['counter'] = \
            SUT.archive_observations[observation]['equal']['count'] + 1

        msg = SUT.check_max_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      record_value)


        self.assertEqual(msg, f"{name}{label} value {record_value} is greater than {value}.\n")

class TestObservationMinCheck(unittest.TestCase):
    def test_observation_not_greater(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        msg = SUT.check_min_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      value)

        self.assertEqual(msg, "")

    def test_observation_less_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int
        record_value = 55 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        msg = SUT.check_min_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      record_value)

        self.assertEqual(msg, "")

    def test_observation_less_with_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99 # ToDo: make random int
        record_value = 55 # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_engine, config)

        SUT.archive_observations[observation]['equal']['counter'] = \
            SUT.archive_observations[observation]['equal']['count'] + 1

        msg = SUT.check_min_value(name,
                                     label,
                                      SUT.archive_observations[observation]['equal'],
                                      record_value)


        self.assertEqual(msg, f"{name}{label} value {record_value} is less than {value}.\n")

if __name__ == '__main__':
    #test_suite = unittest.TestSuite()
    #test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    #unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
