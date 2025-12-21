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
from collections import namedtuple

from user.notify import Logger
from user.pushover import PushOver

class TestTest(unittest.IsolatedAsyncioTestCase):
    # This is a bit silly test, but it is a good template for testing HTTP Post
    # ToDo: change call_count = 1 to called_once_with
    async def test_error_sending_notification(self):
        mock_logger = mock.Mock(spec=Logger)

        config_dict = {}
        config = configobj.ConfigObj(config_dict)

        SUT = PushOver(mock_logger, config)

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
