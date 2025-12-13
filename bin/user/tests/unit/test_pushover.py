#
#    Copyright (c) 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring

import unittest
import mock

import configobj
import random
import string
import time

from collections import namedtuple

from user.notify import Notify, Logger

def random_string(length=32):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])

def setup_config_dict(binding,
                      observation,
                      check_type,
                      label=None,
                      name=None,
                      count=10,
                      wait_time=3600,
                      return_notification=True,
                      value=None):
    config_dict = {
        'Notify':
        {
            'PushOver': {
                'extension': random_string(),
            },
            binding:
            {
                observation:
                {
                    check_type:
                    {
                        'count': count,
                        'wait_time': wait_time,
                        'return_notification': return_notification,
                    }
                }
            }
        }
    }

    if label:
        config_dict['Notify'][binding][observation]['label'] = label
    if name:
        config_dict['Notify'][binding][observation]['weewx_name'] = name
    if value:
        config_dict['Notify'][binding][observation][check_type]['value'] = value

    return config_dict

class MockClass():
    def __init__(self, _arg1, _arg2):
        pass

class TestObservationMissing(unittest.TestCase):
    def test_at_startup(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        name = observation

        config_dict = setup_config_dict('archive', observation, 'missing', label)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'missing',
            'threshold_value': None,
            'name': name,
            'label': f" ({label})",
            'current_value': None,
            'type': 'outside',
            'notifications_sent': 1,
            'date_time': None,
        }

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)
                result = SUT.check_missing_value(observation,
                                                 SUT.archive_observations[observation]['name'],
                                                 SUT.archive_observations[observation]['label'],
                                                 SUT.archive_observations[observation]['missing'])

                expected_dict['date_time'] = SUT.missing_observations[observation]['missing_time']
                expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

            self.assertEqual(result, expected_result)
            self.assertIn(observation, SUT.missing_observations)
            self.assertIn('missing_time', SUT.missing_observations[observation])

    def test_past_time_threshold_past_count_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        name = observation
        count = 10  # To do make random int
        now = time.time()

        config_dict = setup_config_dict('archive', observation, 'missing', label, count=count)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'missing',
            'threshold_value': None,
            'name': name,
            'label': f" ({label})",
            'current_value': None,
            'type': 'outside',
            'notifications_sent': 1,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)
                # Missing notification has been 'sent'.
                # Setting to 1, ensures that time threshold has been met.
                SUT.archive_observations[observation]['missing']['last_sent_timestamp'] = 1
                SUT.missing_observations[observation] = {}
                SUT.missing_observations[observation]['missing_time'] = now
                SUT.missing_observations[observation]['notification_count'] = 0

                # Setting to ensure that count threshold has been met.
                SUT.archive_observations[observation]['missing']['counter'] = count - 1

                result = SUT.check_missing_value(observation,
                                                 SUT.archive_observations[observation]['name'],
                                                 SUT.archive_observations[observation]['label'],
                                                 SUT.archive_observations[observation]['missing'])

                self.assertEqual(result, expected_result)
                self.assertIn(observation, SUT.missing_observations)
                self.assertIn('missing_time', SUT.missing_observations[observation])

    def test_past_time_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        count = 10  # To do make random int
        config_dict = setup_config_dict('archive', observation, 'missing', label, count=count)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)
                # Missing notification has been 'sent'.
                # Setting to 1, ensures that time threshold has been met.
                SUT.archive_observations[observation]['missing']['last_sent_timestamp'] = 1
                # Setting to ensure that count threshold has NOT been met.
                SUT.archive_observations[observation]['missing']['counter'] = 0

                result = SUT.check_missing_value(observation,
                                                 SUT.archive_observations[observation]['name'],
                                                 SUT.archive_observations[observation]['label'],
                                                 SUT.archive_observations[observation]['missing'])

                self.assertIsNone(result)
                self.assertIn(observation, SUT.missing_observations)

    def test_past_count_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        count = 10  # To do make random int
        config_dict = setup_config_dict('archive', observation, 'missing', label, count=count)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)
                # Missing notification has been 'sent'.
                # Setting to 1, ensures that time threshold has NOT been met.
                SUT.archive_observations[observation]['missing']['last_sent_timestamp'] = \
                    int(time.time())
                # Setting to ensure that count threshold has been met.
                SUT.archive_observations[observation]['missing']['counter'] = count - 1

                result = SUT.check_missing_value(observation,
                                                 SUT.archive_observations[observation]['name'],
                                                 SUT.archive_observations[observation]['label'],
                                                 SUT.archive_observations[observation]['missing'])

                self.assertIsNone(result)

class TestObservationReturned(unittest.TestCase):
    def test_observation_not_missing(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = random_string()
        name = observation
        value = 99.9  # ToDo: make random

        config_dict = setup_config_dict(binding, observation, 'missing', label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.missing_observations = {}

            result = SUT.check_value_returned(observation,
                                              name,
                                              label,
                                              SUT.archive_observations[observation]['missing'],
                                              value)

            self.assertIsNone(result)

    def test_observation_missing_no_notification(self):
        mock_engine = mock.Mock()
        now = int(time.time())

        binding = 'archive'
        observation = random_string()
        label = random_string()
        name = observation
        value = 99.9  # ToDo: make random

        config_dict = setup_config_dict(binding, observation, 'missing', label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.missing_observations = {
                observation: {
                    'notification_count': 0,
                    'missing_time': now,
                }
            }

            result = SUT.check_value_returned(observation,
                                              name,
                                              label,
                                              SUT.archive_observations[observation]['missing'],
                                              value)

            self.assertIsNone(result)

    def test_observation_missing_with_notification(self):
        mock_engine = mock.Mock()
        now = int(time.time())
        notification_count = 99  # ToDo: make random

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99.9  # ToDo: make random

        config_dict = setup_config_dict(binding, observation, 'missing', label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'missing',
            'threshold_value': None,
            'name': name,
            'label': label,
            'current_value': value,
            'type': 'within',
            'notifications_sent': notification_count,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.missing_observations = {
                observation: {
                    'notification_count': notification_count,
                    'missing_time': now,
                }
            }

            SUT.archive_observations[observation]['missing']['counter'] = 1

            result = SUT.check_value_returned(observation,
                                              name,
                                              label,
                                              SUT.archive_observations[observation]['missing'],
                                              value)

            self.assertEqual(result, expected_result)

    def test_observation_missing_notification_not_requested(self):
        mock_engine = mock.Mock()
        now = int(time.time())
        notification_count = 99  # ToDo: make random

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99.9  # ToDo: make random

        config_dict = setup_config_dict(binding, observation, 'missing', label=label, name=name, return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.missing_observations = {
                observation: {
                    'notification_count': notification_count,
                    'missing_time': now,
                }
            }

            result = SUT.check_value_returned(observation,
                                              name,
                                              label,
                                              SUT.archive_observations[observation]['missing'],
                                              value)

            self.assertIsNone(result)

class TestObservationEqualCheck(unittest.TestCase):
    def test_observation_equal_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = \
                time.time()
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = 0

            result = SUT.check_equal_value(name,
                                           label,
                                           SUT.archive_observations[observation]['equal'],
                                           value)

            self.assertIsNone(result)

    def test_observation_equal_with_notification(self):
        mock_engine = mock.Mock()
        now = time.time()
        notification_count = 1  # ToDo: make randome

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'equal',
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': value,
            'type': 'within',
            'notifications_sent': notification_count,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = \
                notification_count
            SUT.archive_observations[observation]['equal']['counter'] = 1

            result = SUT.check_equal_value(name,
                                           label,
                                           SUT.archive_observations[observation]['equal'],
                                           value)

            self.assertEqual(result, expected_result)

    def test_observation_equal_notification_not_requested(self):
        mock_engine = mock.Mock()
        now = time.time()
        notification_count = 1  # ToDo: make randome

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value,
                                        return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = \
                notification_count

            result = SUT.check_equal_value(name,
                                           label,
                                           SUT.archive_observations[observation]['equal'],
                                           value)

            self.assertIsNone(result)

    def test_observation_not_equal_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int
        record_value = 55  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            result = SUT.check_equal_value(name,
                                           label,
                                           SUT.archive_observations[observation]['equal'],
                                           record_value)

            self.assertIsNone(result)

    def test_observation_not_equal_with_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int
        record_value = 55  # ToDo: make random int
        now = time.time()
        notification_count = 0

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'equal',
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': record_value,
            'type': 'outside',
            'notifications_sent': notification_count + 1,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['counter'] = \
                SUT.archive_observations[observation]['equal']['count'] + 1
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = notification_count

            result = SUT.check_equal_value(name,
                                           label,
                                           SUT.archive_observations[observation]['equal'],
                                           record_value)

            self.assertEqual(result, expected_result)

class TestObservationMaxCheck(unittest.TestCase):
    def test_observation_not_greater_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = \
                time.time()
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = 0

            result = SUT.check_max_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         value)

            self.assertIsNone(result)

    def test_observation_not_greater_with_notification(self):
        mock_engine = mock.Mock()
        now = time.time()
        notification_count = 1  # ToDo: make random

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'max',
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': value,
            'type': 'within',
            'notifications_sent': notification_count,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = \
                notification_count
            SUT.archive_observations[observation]['equal']['counter'] = 1

            result = SUT.check_max_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         value)

            self.assertEqual(result, expected_result)

    def test_observation_not_greater_notification_not_requested(self):
        mock_engine = mock.Mock()
        now = time.time()
        notification_count = 1  # ToDo: make random

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value,
                                        return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = \
                notification_count

            result = SUT.check_max_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         value)

            self.assertIsNone(result)

    def test_observation_greater_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int
        record_value = 155  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            result = SUT.check_max_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         record_value)

            self.assertIsNone(result)

    def test_observation_greater_with_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int
        record_value = 155  # ToDo: make random int
        now = time.time()
        notification_count = 0

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'max',
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': record_value,
            'type': 'outside',
            'notifications_sent': notification_count + 1,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['counter'] = \
                SUT.archive_observations[observation]['equal']['count'] + 1

            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = notification_count

            result = SUT.check_max_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         record_value)

            self.assertEqual(result, expected_result)

class TestObservationMinCheck(unittest.TestCase):
    def test_observation_not_greater_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = \
                time.time()
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = 0

            result = SUT.check_min_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         value)

            self.assertIsNone(result)

    def test_observation_not_greater_with_notification(self):
        mock_engine = mock.Mock()
        now = time.time()
        notification_count = 1  # ToDo: make random

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'min',
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': value,
            'type': 'within',
            'notifications_sent': notification_count,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = \
                notification_count
            SUT.archive_observations[observation]['equal']['counter'] = 1

            result = SUT.check_min_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         value)

            self.assertEqual(result, expected_result)

    def test_observation_not_greater_notification_not_requested(self):
        mock_engine = mock.Mock()
        now = time.time()
        notification_count = 1  # ToDo: make random

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value,
                                        return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = \
                notification_count

            result = SUT.check_min_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         value)

            self.assertIsNone(result)

    def test_observation_less_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int
        record_value = 55  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            result = SUT.check_min_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         record_value)

            self.assertIsNone(result)

    def test_observation_less_with_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int
        record_value = 55  # ToDo: make random int
        now = time.time()
        notification_count = 0

        config_dict = setup_config_dict(binding,
                                        observation,
                                        'equal',
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': 'min',
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': record_value,
            'type': 'outside',
            'notifications_sent': notification_count + 1,
            'date_time': now,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)
            SUT.archive_observations[observation]['equal']['counter'] = \
                SUT.archive_observations[observation]['equal']['count'] + 1

            SUT.archive_observations[observation]['equal']['threshold_passed'] = {}
            SUT.archive_observations[observation]['equal']['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation]['equal']['threshold_passed']['notification_count'] = notification_count

            result = SUT.check_min_value(name,
                                         label,
                                         SUT.archive_observations[observation]['equal'],
                                         record_value)

            self.assertEqual(result, expected_result)

if __name__ == '__main__':
    # test_suite = unittest.TestSuite()
    # test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    # unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
