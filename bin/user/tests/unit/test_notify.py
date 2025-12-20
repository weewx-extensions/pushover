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

# ToDo: change call_count = 1 to called_once_with

class TestNotify(unittest.IsolatedAsyncioTestCase):
    async def test_process_data_template(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        data = {
            observation: random.random(),
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

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
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

    async def test_process_data_min_within(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'min'
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        value = threshold_value + 1

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 1)
                                                    self.assertEqual(mock_check_outside.call_count, 0)
                                                    self.assertEqual(mock_create_task.call_count, 1)
                                                    self.assertEqual(mock_wait.call_count, 1)


    async def test_process_data_min_outside(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'min'
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        value = threshold_value - 1

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 0)
                                                    self.assertEqual(mock_check_outside.call_count, 1)
                                                    self.assertEqual(mock_create_task.call_count, 0)
                                                    self.assertEqual(mock_wait.call_count, 0)

    async def test_process_data_max_within(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'max'
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        value = threshold_value - 1

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 1)
                                                    self.assertEqual(mock_check_outside.call_count, 0)
                                                    self.assertEqual(mock_create_task.call_count, 1)
                                                    self.assertEqual(mock_wait.call_count, 1)

    async def test_process_data_max_outside(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'max'
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        value = threshold_value + 1

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 0)
                                                    self.assertEqual(mock_check_outside.call_count,1)
                                                    self.assertEqual(mock_create_task.call_count, 0)
                                                    self.assertEqual(mock_wait.call_count, 0)

    async def test_process_data_equal_within(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'equal'
        observation = random_string()
        threshold_value = random.randint(1, 99)
        label = random_string()
        value = threshold_value

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 1)
                                                    self.assertEqual(mock_check_outside.call_count, 0)
                                                    self.assertEqual(mock_create_task.call_count, 1)
                                                    self.assertEqual(mock_wait.call_count, 1)

    async def test_process_data_equal_outside(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'equal'
        observation = random_string()
        threshold_value = random.randint(1, 99)
        label = random_string()
        value = threshold_value + 1

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 0)
                                                    self.assertEqual(mock_check_outside.call_count, 1)
                                                    self.assertEqual(mock_create_task.call_count, 0)
                                                    self.assertEqual(mock_wait.call_count, 0)

    async def test_process_data_observation_returns(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'missing'
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        value = random.random()

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 1)
                                                    self.assertEqual(mock_check_outside.call_count, 0)
                                                    self.assertEqual(mock_create_task.call_count, 1)
                                                    self.assertEqual(mock_wait.call_count, 1)

    async def test_process_data_observation_gone_missing(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'missing'
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        value = random.random()

        data = {
            random_string(): value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = None

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 0)
                                                    self.assertEqual(mock_check_outside.call_count, 1)
                                                    self.assertEqual(mock_create_task.call_count, 0)
                                                    self.assertEqual(mock_wait.call_count, 0)

    async def test_process_data_observation_gone_missing_succeeds(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = 'missing'
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        value = random.random()

        data = {
            random_string(): value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = 'foo'

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 0)
                                                    self.assertEqual(mock_check_outside.call_count, 1)
                                                    self.assertEqual(mock_create_task.call_count, 1)
                                                    self.assertEqual(mock_wait.call_count, 1)
                                                    print('done')

    async def test_process_data_within_succeeds(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = random.choice(['min', 'max', 'equal'])
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        if threshold_type == 'min':
            value = threshold_value + 1
        else:
            value = threshold_value - 1

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = 'foo'

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 1)
                                                    self.assertEqual(mock_check_outside.call_count, 0)
                                                    self.assertEqual(mock_create_task.call_count, 1)
                                                    self.assertEqual(mock_wait.call_count, 1)

    async def test_process_data_outside_succeeds(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = random.choice(['min', 'max', 'equal'])
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        if threshold_type == 'min':
            value = threshold_value - 1
        else:
            value = threshold_value + 1

        data = {
            observation: value,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task') as mock_create_task:
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass
                                                    mock_check_outside.return_value = 'foo'

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 0)
                                                    self.assertEqual(mock_check_outside.call_count, 1)
                                                    self.assertEqual(mock_create_task.call_count, 1)
                                                    self.assertEqual(mock_wait.call_count, 1)

    async def test_process_data_observation_is_none(self):
        mock_engine = mock.Mock()
        now = time.time()

        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        threshold_value = random.random()
        label = random_string()
        data = {
            observation: None,
        }
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=threshold_value)
        config = configobj.ConfigObj(config_dict)

        observations = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('asyncio.create_task'):
                with mock.patch('asyncio.wait') as mock_wait:
                    with mock.patch('user.notify.Logger', spec=Logger):
                        with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                            with mock.patch.object(Notify, 'check_within') as mock_check_within:
                                with mock.patch.object(Notify, 'check_outside') as mock_check_outside:
                                    with mock.patch.object(MockClass, 'timeout', new_callable=mock.Mock):
                                        with mock.patch.object(MockClass, 'initialize', new_callable=mock.Mock):
                                            with mock.patch.object(MockClass, 'send_notification', new_callable=mock.Mock):
                                                with mock.patch.object(MockClass, 'finalize', new_callable=mock.AsyncMock):
                                                    mock_time.time.return_value = now
                                                    mock_wait.return_value = ([mock.Mock()], [mock.Mock()])
                                                    mock_weeutil.get_object.return_value = MockClass

                                                    SUT = Notify(mock_engine, config)
                                                    if binding_type == 'archive':
                                                        observations = SUT.archive_observations
                                                    if binding_type == 'loop':
                                                        observations = SUT.loop_observations

                                                    await SUT._process_data(False, data, observations)

                                                    self.assertEqual(mock_check_within.call_count, 0)
                                                    self.assertEqual(mock_check_outside.call_count, 0)
                                                    self.assertEqual(mock_wait.call_count, 0)

    async def test_check_within_threshold_did_not_leave(self):
        mock_engine = mock.Mock()
        now = time.time()
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value)
        config = configobj.ConfigObj(config_dict)

        result = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('user.notify.Logger', spec=Logger):
                with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                    mock_time.time.return_value = now
                    mock_weeutil.get_object.return_value = MockClass

                    SUT = Notify(mock_engine, config)

                    if binding_type == 'archive':
                        SUT.archive_observations[observation][threshold_type]['counter'] = 0
                        SUT.archive_observations[observation][threshold_type]['threshold_passed'] = {}
                        SUT.archive_observations[observation][threshold_type]['threshold_passed']['timestamp'] = now
                        SUT.archive_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 0
                        result = SUT.check_within(threshold_type,
                                                  observation,
                                                  label,
                                                  SUT.archive_observations[observation][threshold_type],
                                                  value)

                    if binding_type == 'loop':
                        SUT.loop_observations[observation][threshold_type]['counter'] = 0
                        SUT.loop_observations[observation][threshold_type]['threshold_passed'] = {}
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['timestamp'] = now
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 0
                        result = SUT.check_within(threshold_type,
                                                  observation,
                                                  label,
                                                  SUT.loop_observations[observation][threshold_type],
                                                  value)

                    self.assertIsNone(result)

    async def test_check_within_threshold_no_notifications_sent(self):
        mock_engine = mock.Mock()
        now = time.time()
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value)
        config = configobj.ConfigObj(config_dict)

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
                        result = SUT.check_within(threshold_type,
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
                        result = SUT.check_within(threshold_type,
                                                  observation,
                                                  label,
                                                  SUT.loop_observations[observation][threshold_type],
                                                  value)

                    self.assertIsNone(result)

    async def test_check_within_threshold_return_notification_not_configured(self):
        mock_engine = mock.Mock()
        now = time.time()
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value, return_notification=False)
        config = configobj.ConfigObj(config_dict)

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
                        SUT.archive_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 1
                        result = SUT.check_within(threshold_type,
                                                  observation,
                                                  label,
                                                  SUT.archive_observations[observation][threshold_type],
                                                  value)

                    if binding_type == 'loop':
                        SUT.loop_observations[observation][threshold_type]['counter'] = \
                            SUT.loop_observations[observation][threshold_type]['count'] + 1
                        SUT.loop_observations[observation][threshold_type]['threshold_passed'] = {}
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['timestamp'] = now
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 1
                        result = SUT.check_within(threshold_type,
                                                  observation,
                                                  label,
                                                  SUT.loop_observations[observation][threshold_type],
                                                  value)

                    self.assertIsNone(result)

    async def test_check_within_threshold_notification_sent(self):
        mock_engine = mock.Mock()
        now = time.time()
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])
        if threshold_type == 'missing':
            threshold_value = None
        else:
            threshold_value = int(value)

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': threshold_type,
            'threshold_value': threshold_value,
            'name': observation,
            'label': label,
            'current_value': value,
            'type': 'within',
            'notifications_sent': 1,
            'date_time': now,
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
                        SUT.archive_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 1
                        result = SUT.check_within(threshold_type,
                                                  observation,
                                                  label,
                                                  SUT.archive_observations[observation][threshold_type],
                                                  value)

                    if binding_type == 'loop':
                        SUT.loop_observations[observation][threshold_type]['counter'] = \
                            SUT.loop_observations[observation][threshold_type]['count'] + 1
                        SUT.loop_observations[observation][threshold_type]['threshold_passed'] = {}
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['timestamp'] = now
                        SUT.loop_observations[observation][threshold_type]['threshold_passed']['notification_count'] = 1
                        result = SUT.check_within(threshold_type,
                                                  observation,
                                                  label,
                                                  SUT.loop_observations[observation][threshold_type],
                                                  value)

                    self.assertEqual(result, expected_result)

    async def test_check_outside_threshold_on_first_leaving(self):
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

        result = None
        expected_dict = {
            'timestamp': int(now),
            'notification_count': 0,
        }

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('user.notify.Logger', spec=Logger):
                with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                    mock_time.time.return_value = now
                    mock_weeutil.get_object.return_value = MockClass

                    SUT = Notify(mock_engine, config)

                    if binding_type == 'archive':
                        SUT.archive_observations[observation][threshold_type]['counter'] = 0
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.archive_observations[observation][threshold_type],
                                                   value)

                    if binding_type == 'loop':
                        SUT.loop_observations[observation][threshold_type]['counter'] = 0
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.loop_observations[observation][threshold_type],
                                                   value)

                    self.assertIsNone(result)
                    if binding_type == 'archive':
                        self.assertDictEqual(SUT.archive_observations[observation][threshold_type]['threshold_passed'], expected_dict)
                    if binding_type == 'loop':
                        self.assertDictEqual(SUT.loop_observations[observation][threshold_type]['threshold_passed'], expected_dict)

    async def test_check_outside_threshold_wait_time_not_met(self):
        mock_engine = mock.Mock()
        now = 0
        first_check = False
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value)
        config = configobj.ConfigObj(config_dict)

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
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.archive_observations[observation][threshold_type],
                                                   value)

                    if binding_type == 'loop':
                        SUT.loop_observations[observation][threshold_type]['counter'] = \
                            SUT.loop_observations[observation][threshold_type]['count'] + 1
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.loop_observations[observation][threshold_type],
                                                   value)

                    self.assertIsNone(result)

    async def test_check_outside_threshold_first_time_checking(self):
        mock_engine = mock.Mock()
        now = time.time()
        first_check = True
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])
        if threshold_type == 'missing':
            threshold_value = None
        else:
            threshold_value = int(value)

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': threshold_type,
            'threshold_value': threshold_value,
            'name': observation,
            'label': label,
            'current_value': value,
            'type': 'outside',
            'notifications_sent': 1,
            'date_time': now,
            'first_check': True,
        }
        expected_result = namedtuple('ExpectedResukt', expected_dict.keys())(**expected_dict)
        result = None
        expected_dict = {
            'timestamp': int(now),
            'notification_count': 1,
        }

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

    async def test_check_outside_threshold_count_not_met(self):
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

        result = None

        with mock.patch('user.notify.time') as mock_time:
            with mock.patch('user.notify.Logger', spec=Logger):
                with mock.patch('user.notify.weeutil.weeutil') as mock_weeutil:
                    mock_time.time.return_value = now
                    mock_weeutil.get_object.return_value = MockClass

                    SUT = Notify(mock_engine, config)

                    if binding_type == 'archive':
                        SUT.archive_observations[observation][threshold_type]['counter'] = \
                            SUT.archive_observations[observation][threshold_type]['count'] - 3
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.archive_observations[observation][threshold_type],
                                                   value)

                    if binding_type == 'loop':
                        SUT.loop_observations[observation][threshold_type]['counter'] = \
                            SUT.loop_observations[observation][threshold_type]['count'] - 3
                        result = SUT.check_outside(first_check,
                                                   threshold_type,
                                                   observation,
                                                   label,
                                                   SUT.loop_observations[observation][threshold_type],
                                                   value)

                    self.assertIsNone(result)

    async def test_check_outside_threshold(self):
        mock_engine = mock.Mock()
        now = time.time()
        first_check = False
        threshold_type = random.choice(['missing', 'min', 'max', 'equal'])
        observation = random_string()
        label = random_string()
        value = random.random()
        binding_type = random.choice(['archive', 'loop'])
        if threshold_type == 'missing':
            threshold_value = None
        else:
            threshold_value = int(value)

        config_dict = setup_config_dict(binding_type, observation, threshold_type, label, value=value)
        config = configobj.ConfigObj(config_dict)

        expected_dict = {
            'threshold_type': threshold_type,
            'threshold_value': threshold_value,
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

if __name__ == '__main__':
    test_suite = unittest.TestSuite()
    # test_suite.addTest(TestNotify('test_process_data_observation_is_none'))
    # test_suite.addTest(TestNotify('test_process_data_outside_succeeds'))
    # test_suite.addTest(TestNotify('test_process_data_within_succeeds'))
    # test_suite.addTest(TestNotify('test_process_data_observation_gone_missing_succeeds'))
    # test_suite.addTest(TestNotify('test_process_data_observation_gone_missing'))
    # test_suite.addTest(TestNotify('test_process_data_observation_returns'))
    # test_suite.addTest(TestNotify('test_process_data_equal_outside'))
    # test_suite.addTest(TestNotify('test_process_data_equal_within'))
    # test_suite.addTest(TestNotify('test_process_data_max_outside'))
    # test_suite.addTest(TestNotify('test_process_data_max_within'))
    # test_suite.addTest(TestNotify('test_process_data_min_outside'))
    # test_suite.addTest(TestNotify('test_process_data_min_within'))

    # unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
