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
from collections import namedtuple
import random
import string
import time

from user.notify import Logger
from user.pushover import Pushover

def random_string(length=32):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])

class TestPushover(unittest.TestCase):
    def test_throttle_notification(self):
        mock_logger = mock.Mock(spec=Logger)
        now = time.time()

        config_dict = {}
        config = configobj.ConfigObj(config_dict)

        with mock.patch('user.pushover.time') as mock_time:
            mock_time.time.return_value = now

            SUT = Pushover(mock_logger, config)

            result = SUT.throttle_notification()

            print(result)
            print('done')

    def test_check_response_with_success_200(self):
        mock_logger = mock.Mock(spec=Logger)

        mock_response = mock.Mock(name='mock_response')
        mock_response.code = 200

        now = time.time()

        config_dict = {}
        config = configobj.ConfigObj(config_dict)

        msg_data_dict = {
            'threshold_type': random_string(),
            'type': random_string(),
            'date_time': random.randint(10000, 20000),
            'weewx_name': random_string(),
            'label': random_string(),
            'threshold_value': random.randint(100, 150),
            'current_value': random.randint(50, 200),
            'notifications_sent': random.randint(200, 201),
        }
        msg_data = namedtuple('MsgData', msg_data_dict.keys())(**msg_data_dict)

        with mock.patch('user.pushover.json') as mock_json:
            with mock.patch('user.pushover.time') as mock_time:
                mock_json.loads.return_value = {'errors': ['Error One', 'Error Two']}
                mock_time.time.return_value = now

                SUT = Pushover(mock_logger, config)

                result = SUT._check_response(mock_response, msg_data)

                self.assertTrue(result)
                self.assertEqual(SUT.client_error_timestamp, 0)
                self.assertEqual(SUT.client_error_last_logged, 0)
                self.assertEqual(SUT.server_error_timestamp, 0)
                self.assertEqual(mock_logger.logerr.call_count, 0)

    def test_check_response_with_error_4xx(self):
        mock_logger = mock.Mock(spec=Logger)

        mock_response = mock.Mock(name='mock_response')
        mock_response.code = random.randint(400, 499)

        now = time.time()

        config_dict = {}
        config = configobj.ConfigObj(config_dict)

        msg_data_dict = {
            'threshold_type': random_string(),
            'type': random_string(),
            'date_time': random.randint(10000, 20000),
            'weewx_name': random_string(),
            'label': random_string(),
            'threshold_value': random.randint(100, 150),
            'current_value': random.randint(50, 200),
            'notifications_sent': random.randint(200, 201),
        }
        msg_data = namedtuple('MsgData', msg_data_dict.keys())(**msg_data_dict)

        with mock.patch('user.pushover.json') as mock_json:
            with mock.patch('user.pushover.time') as mock_time:
                mock_json.loads.return_value = {'errors': ['Error One', 'Error Two']}
                mock_time.time.return_value = now

                SUT = Pushover(mock_logger, config)

                result = SUT._check_response(mock_response, msg_data)

                self.assertFalse(result)
                self.assertEqual(SUT.client_error_timestamp, now)
                self.assertEqual(SUT.client_error_last_logged, now)
                self.assertEqual(SUT.server_error_timestamp, 0)
                self.assertEqual(mock_logger.logerr.call_count, 2)

    def test_check_response_with_error_5xx(self):
        mock_logger = mock.Mock(spec=Logger)

        mock_response = mock.Mock(name='mock_response')
        mock_response.code = random.randint(500, 599)

        now = time.time()

        config_dict = {}
        config = configobj.ConfigObj(config_dict)

        msg_data_dict = {
            'threshold_type': random_string(),
            'type': random_string(),
            'date_time': random.randint(10000, 20000),
            'weewx_name': random_string(),
            'label': random_string(),
            'threshold_value': random.randint(100, 150),
            'current_value': random.randint(50, 200),
            'notifications_sent': random.randint(200, 201),
        }
        msg_data = namedtuple('MsgData', msg_data_dict.keys())(**msg_data_dict)

        with mock.patch('user.pushover.json') as mock_json:
            with mock.patch('user.pushover.time') as mock_time:
                mock_json.loads.return_value = {'errors': ['Error One', 'Error Two']}
                mock_time.time.return_value = now

                SUT = Pushover(mock_logger, config)

                result = SUT._check_response(mock_response, msg_data)

                self.assertFalse(result)
                self.assertEqual(SUT.client_error_timestamp, 0)
                self.assertEqual(SUT.client_error_last_logged, 0)
                self.assertEqual(SUT.server_error_timestamp, now)
                self.assertEqual(mock_logger.logerr.call_count, 2)

class TestPushoverAsync(unittest.IsolatedAsyncioTestCase):
    # This is a bit silly test, but it is a good template for testing HTTP Post
    # ToDo: change call_count = 1 to called_once_with
    async def test_error_sending_notification(self):
        mock_logger = mock.Mock(spec=Logger)

        config_dict = {}
        config = configobj.ConfigObj(config_dict)

        SUT = Pushover(mock_logger, config)

        msg_data_dict = {
            'threshold_type': 'equal',
            'type': 'outside',
            'date_time': 1,
            'weewx_name': 'foo',
            'label': 'foo',
            'threshold_value': 101,
            'current_value': 102,
            'notifications_sent': 201,
        }
        msg_data = namedtuple('MsgData', msg_data_dict.keys())(**msg_data_dict)

        mock_response = mock.Mock(name='mock_response')
        mock_response.code = 400

        with mock.patch('user.pushover.json') as mock_json:
            with mock.patch('user.pushover.time'):
                with mock.patch('http.client.HTTPSConnection') as mock_connection:
                    mock_json.loads.return_value = {'errors': ['Error One', 'Error Two']}
                    mock_connection_instance = mock_connection.return_value
                    mock_connection_instance.getresponse.return_value = mock_response

                    result = await SUT.send_notification(msg_data)

                    self.assertFalse(result)
                    self.assertEqual(mock_connection.call_count, 1)
                    self.assertEqual(mock_connection_instance.request.call_count, 1)
                    self.assertEqual(mock_connection_instance.getresponse.call_count, 1)
                    self.assertEqual(mock_response.read.call_count, 1)

if __name__ == '__main__':
    # test_suite = unittest.TestSuite()
    # test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    # unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
