#
#    Copyright (c) 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=wrong-import-order
# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring
# pylint: disable=protected-access

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

    @property
    def timeout(self):
        return random.randint(1, 100)

    def initialize(self):
        pass

    def send_notification(self, _arg1):
        pass

    async def finalize(self):
        pass

class TestNotify(unittest.IsolatedAsyncioTestCase):
    async def test_process_data(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'min'
        observation = random_string()
        value = random.random()
        label = random_string()
        data = {
            observation: value,
        }

        config_dict = setup_config_dict('archive', observation, threshold_type, label, value=value - 1)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task'):
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within'):
                                with mock.patch.object(Notify, 'check_outside'):
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass

                                                    SUT = Notify(mock_engine, config)

                                                    await SUT._process_data(False, data, SUT.archive_observations)

    async def test_process_data_min_within(self):
        pass

    async def test_process_data_min_outside(self):
        pass

    async def test_process_data_max_within(self):
        pass

    async def test_process_data_max_outside(self):
        pass

    async def test_process_data_equal_within(self):
        pass

    async def test_process_data_equal_outside(self):
        pass

    async def test_process_data_observation_returns(self):
        pass

    async def test_process_data_observation_gone_missing(self):
        pass

    async def test_process_data_observation_gone_missing_succeeds(self):
        pass

    async def test_process_data_within_succeeds(self):
        pass

    def test_process_data_outside_succeeds(self):
        pass

    async def test_process_data_observeraion_is_none(self):
        pass

    async def test_check_within_threshold_did_not_leave(self):
        pass

    async def test_check_within_threshold_no_notifications_sent(self):
        pass

    async def test_check_within_threshold_return_notification_not_configured(self):
        pass

    async def test_check_within_threshold_notification_sent(self):
        pass

    async def test_check_outside_threshold_on_first_leaving(self):
        pass

    async def test_check_outside_threshold_wait_time_not_met(self):
        pass

    async def test_check_outside_threshold_first_time_checking(self):
        pass

    async def test_check_outside_threshold_count_not_met(self):
        pass

    async def test_check_outside_threshold(self):
        mock_engine = mock.Mock()
        now = time.time()
        first_check = False
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': threshold_type,
            'threshold_value': int(value),
            'name': observation,
            'label': label,
            'current_value': value,
            'type': 'outside',
            'notifications_sent': 1,
            'date_time': now,
            'first_check': False,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)
        result = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('user.notify.Logger', spec=Logger):
                with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                    mock_time.time.return_value = now
                    mock_weeutil.get_object.return_value = MockClass

                    SUT = Notify(mock_engine, config)

                    if binding_type == 'archive':
                        SUT.archive_observations[observation][threshold_type]['counter'] = \
                            SUT.archive_observations[observation][threshold_type]['count'] + 1
                        SUT.archive_observations[observation][threshold_type]['threshold_passed'] = {}
                        SUT.archive_observations[observation][threshold_type]['threshold_passed']['timestamp'] = now
                        SUT.archive_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 0
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.archive_observations[observation][threshold_type],
                                                   value)

                    if binding_type == 'loop':
                        SUT.loop_observations[observation][threshold_type]['counter'] = \
                            SUT.loop_observations[observation][threshold_type]['count'] + 1
                        SUT.loop_observations[observation][threshold_type]['threshold_passed'] = {}
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['timestamp'] = now
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 0
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.loop_observations[observation][threshold_type],
                                                   value)

                    self.assertEqual(result, expected_result)

@unittest.skip('todo - delete')
class TestObservationMissing(unittest.TestCase):
    threshold_type = 'missing'

    def test_at_startup(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        name = observation

        config_dict = setup_config_dict('archive', observation, TestObservationMissing.threshold_type, label)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationMissing.threshold_type,
            'threshold_value': None,
            'name': name,
            'label': f" ({label})",
            'current_value': None,
            'type': 'outside',
            'notifications_sent': 1,
            'date_time': None,
            'first_check': True,
        }

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)
                result = SUT.check_outside(True,
                                           TestObservationMissing.threshold_type,
                                           SUT.archive_observations[observation]['name'],
                                           SUT.archive_observations[observation]['label'],
                                           SUT.archive_observations[observation][TestObservationMissing.threshold_type],
                                           None)

                expected_dict['date_time'] = \
                    SUT.archive_observations[observation][TestObservationMissing.threshold_type]['threshold_passed']['timestamp']
                expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

            self.assertEqual(result, expected_result)

    def test_past_time_threshold_past_count_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        name = observation
        count = 10  # To do make random int
        now = time.time()

        config_dict = setup_config_dict('archive', observation, TestObservationMissing.threshold_type, label, count=count)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationMissing.threshold_type,
            'threshold_value': None,
            'name': name,
            'label': f" ({label})",
            'current_value': None,
            'type': 'outside',
            'notifications_sent': 1,
            'date_time': now,
            'first_check': False,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)

                # Missing notification has been 'sent'.
                # Setting to 1, ensures that time threshold has been met.
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['threshold_passed'] = {}
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['threshold_passed']['timestamp'] = now
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['threshold_passed']['notification_count']\
                    = 0

                # Setting to ensure that count threshold has been met.
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['counter'] = count - 1

                result = SUT.check_outside(False,
                                           TestObservationMissing.threshold_type,
                                           SUT.archive_observations[observation]['name'],
                                           SUT.archive_observations[observation]['label'],
                                           SUT.archive_observations[observation][TestObservationMissing.threshold_type],
                                           None)

                self.assertEqual(result, expected_result)

    def test_past_time_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        count = 10  # To do make random int
        config_dict = setup_config_dict('archive', observation, TestObservationMissing.threshold_type, label, count=count)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)

                # Missing notification has been 'sent'.
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['last_sent_timestamp'] = 1
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['threshold_passed'] = {}
                # Setting to 1, ensures that time threshold has been met.
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['threshold_passed']['timestamp'] = 1
                # Setting to ensure that count threshold has NOT been met.
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['threshold_passed']['counter'] = 0

                result = SUT.check_outside(False,
                                           TestObservationMissing.threshold_type,
                                           SUT.archive_observations[observation]['name'],
                                           SUT.archive_observations[observation]['label'],
                                           SUT.archive_observations[observation][TestObservationMissing.threshold_type],
                                           None)

                self.assertIsNone(result)

    def test_past_count_threshold(self):
        mock_engine = mock.Mock()

        observation = random_string()
        label = random_string()
        count = 10  # To do make random int
        config_dict = setup_config_dict('archive', observation, TestObservationMissing.threshold_type, label, count=count)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.Logger', spec=Logger):
            with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                mock_weeutil.get_object.return_value = MockClass
                SUT = Notify(mock_engine, config)

                # Missing notification has been 'sent'.
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['last_sent_timestamp'] = int(time.time())
                # Setting to ensure that count threshold has been met.
                SUT.archive_observations[observation][TestObservationMissing.threshold_type]['counter'] = count - 1

                result = SUT.check_outside(False,
                                           TestObservationMissing.threshold_type,
                                           SUT.archive_observations[observation]['name'],
                                           SUT.archive_observations[observation]['label'],
                                           SUT.archive_observations[observation][TestObservationMissing.threshold_type],
                                           None)

                self.assertIsNone(result)

@unittest.skip('todo - delete')
class TestObservationReturned(unittest.TestCase):
    threshold_type = 'missing'

    def test_observation_not_missing(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = random_string()
        name = observation
        value = 99.9  # ToDo: make random

        config_dict = setup_config_dict(binding, observation, TestObservationReturned.threshold_type, label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            result = SUT.check_within(TestObservationReturned.threshold_type,
                                      name,
                                      label,
                                      SUT.archive_observations[observation][TestObservationReturned.threshold_type],
                                      value)

            self.assertIsNone(result)

    def test_observation_missing_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = random_string()
        name = observation
        value = 99.9  # ToDo: make random

        config_dict = setup_config_dict(binding, observation, TestObservationReturned.threshold_type, label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            result = SUT.check_within(TestObservationReturned.threshold_type,
                                      name,
                                      label,
                                      SUT.archive_observations[observation][TestObservationReturned.threshold_type],
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

        config_dict = setup_config_dict(binding, observation, TestObservationReturned.threshold_type, label=label, name=name)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationReturned.threshold_type,
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

            SUT.archive_observations[observation][TestObservationReturned.threshold_type]['counter'] = 1
            SUT.archive_observations[observation][TestObservationReturned.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationReturned.threshold_type]['threshold_passed']['notification_count']\
                = notification_count
            SUT.archive_observations[observation][TestObservationReturned.threshold_type]['threshold_passed']['timestamp'] = now

            result = SUT.check_within(TestObservationReturned.threshold_type,
                                      name,
                                      label,
                                      SUT.archive_observations[observation][TestObservationReturned.threshold_type],
                                      value)

            self.assertEqual(result, expected_result)

    def test_observation_missing_notification_not_requested(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99.9  # ToDo: make random

        config_dict = setup_config_dict(binding, observation,
                                        TestObservationReturned.threshold_type,
                                        label=label,
                                        name=name,
                                        return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            result = SUT.check_within(TestObservationReturned.threshold_type,
                                      name,
                                      label,
                                      SUT.archive_observations[observation][TestObservationReturned.threshold_type],
                                      value)

            self.assertIsNone(result)

@unittest.skip('todo - delete')
class TestObservationEqualCheck(unittest.TestCase):
    threshold_type = 'equal'

    def test_observation_equal_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        TestObservationEqualCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['timestamp'] = \
                time.time()
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['notification_count']\
                = 0

            result = SUT.check_outside(False,
                                       TestObservationEqualCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type],
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
                                        TestObservationEqualCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationEqualCheck.threshold_type,
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

            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['counter'] = 1

            result = SUT.check_within(TestObservationEqualCheck.threshold_type,
                                      name,
                                      label,
                                      SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type],
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
                                        TestObservationEqualCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value,
                                        return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count

            result = SUT.check_outside(False,
                                       TestObservationEqualCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type],
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
                                        TestObservationEqualCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            result = SUT.check_outside(False,
                                       TestObservationEqualCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type],
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
                                        TestObservationEqualCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationEqualCheck.threshold_type,
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': record_value,
            'type': 'outside',
            'notifications_sent': notification_count + 1,
            'date_time': now,
            'first_check': False
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['counter'] = \
                SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['count'] + 1
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count

            result = SUT.check_outside(False,
                                       TestObservationEqualCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationEqualCheck.threshold_type],
                                       record_value)

            self.assertEqual(result, expected_result)

@unittest.skip('todo - delete')
class TestObservationMaxCheck(unittest.TestCase):
    threshold_type = 'max'

    def test_observation_not_greater_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        TestObservationMaxCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['timestamp'] = \
                time.time()
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['notification_count']\
                = 0

            result = SUT.check_outside(False,
                                       TestObservationMaxCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type],
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
                                        TestObservationMaxCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationMaxCheck.threshold_type,
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

            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['counter'] = 1

            result = SUT.check_within(TestObservationMaxCheck.threshold_type,
                                      name,
                                      label,
                                      SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type],
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
                                        TestObservationMaxCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value,
                                        return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count

            result = SUT.check_outside(False,
                                       TestObservationMaxCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type],
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
                                        TestObservationMaxCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            result = SUT.check_outside(False,
                                       TestObservationMaxCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type],
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
                                        TestObservationMaxCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationMaxCheck.threshold_type,
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': record_value,
            'type': 'outside',
            'notifications_sent': notification_count + 1,
            'date_time': now,
            'first_check': False,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['counter'] = \
                SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['count'] + 1
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count

            result = SUT.check_outside(False,
                                       TestObservationMaxCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMaxCheck.threshold_type],
                                       record_value)

            self.assertEqual(result, expected_result)

@unittest.skip('todo - delete')
class TestObservationMinCheck(unittest.TestCase):
    threshold_type = 'min'

    def test_observation_not_greater_no_notification(self):
        mock_engine = mock.Mock()

        binding = 'archive'
        observation = random_string()
        label = f' {random_string()}'
        name = observation
        value = 99  # ToDo: make random int

        config_dict = setup_config_dict(binding,
                                        observation,
                                        TestObservationMinCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['timestamp'] = \
                time.time()
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['notification_count']\
                = 0

            result = SUT.check_outside(False,
                                       TestObservationMinCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMinCheck.threshold_type],
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
                                        TestObservationMinCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationMinCheck.threshold_type,
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

            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['counter'] = 1

            result = SUT.check_within(TestObservationMinCheck.threshold_type,
                                      name,
                                      label,
                                      SUT.archive_observations[observation][TestObservationMinCheck.threshold_type],
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
                                        TestObservationMinCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value,
                                        return_notification=False)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count

            result = SUT.check_outside(False,
                                       TestObservationMinCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMinCheck.threshold_type],
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
                                        TestObservationMinCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            result = SUT.check_outside(False,
                                       TestObservationMinCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMinCheck.threshold_type],
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
                                        TestObservationMinCheck.threshold_type,
                                        label=label,
                                        name=name,
                                        value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': TestObservationMinCheck.threshold_type,
            'threshold_value': value,
            'name': name,
            'label': label,
            'current_value': record_value,
            'type': 'outside',
            'notifications_sent': notification_count + 1,
            'date_time': now,
            'first_check': False
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)

        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
            mock_weeutil.get_object.return_value = MockClass
            SUT = Notify(mock_engine, config)

            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['counter'] = \
                SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['count'] + 1
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed'] = {}
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['timestamp'] = now
            SUT.archive_observations[observation][TestObservationMinCheck.threshold_type]['threshold_passed']['notification_count']\
                = notification_count

            result = SUT.check_outside(False,
                                       TestObservationMinCheck.threshold_type,
                                       name,
                                       label,
                                       SUT.archive_observations[observation][TestObservationMinCheck.threshold_type],
                                       record_value)

            self.assertEqual(result, expected_result)

if __name__ == '__main__':
    # test_suite = unittest.TestSuite()
    # test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    # unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
