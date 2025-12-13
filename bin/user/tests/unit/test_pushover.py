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
import json
from collections import namedtuple

from user.notify import Logger
from user.pushover import PushOver

class TestTest(unittest.IsolatedAsyncioTestCase):
    async def test_test(self):
        mock_logger = mock.Mock(spec=Logger)

        config_dict = {}
        config = configobj.ConfigObj(config_dict)

        SUT = PushOver(mock_logger, config)

        foobar = {
            'threshold_type': 'equal',
            'type': 'outside',
            'date_time': 1,
            'name': 'foo',
            'label': 'foo',
            'threshold_value': 101,
            'current_value': 102,
            'notifications_sent': 201,
        }
        msg_data = namedtuple('FooBar', foobar.keys())(**foobar)

        mock_response = mock.Mock(name='mock_response')
        mock_response.code = 400
        response_body = json.dumps({'errors': ['bar01', 'bar02']})
        mock_response.read.return_value = response_body.encode()

        with mock.patch('http.client.HTTPSConnection') as mock_connection:
            mock_connection_instance = mock_connection.return_value
            mock_connection_instance.getresponse.return_value = mock_response

            await SUT.send_notification(msg_data)

        print("done")

if __name__ == '__main__':
    # test_suite = unittest.TestSuite()
    # test_suite.addTest(TestObservationMissing('tests_observation_missing_at_startup'))
    # unittest.TextTestRunner().run(test_suite)

    unittest.main(exit=False)
