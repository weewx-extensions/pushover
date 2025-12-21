#
#    Copyright (c) 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
'''
Send a notification via pushover, pushover.net

[Notify]

    notifier = PushOver

    # Configuration data for the notification provider, PushOver.
    # The value of this section name must match the value of the 'notifier =' option.
    [[PushOver]]
        # The extension (service) to use.
        extension = user.pushover.PushOver

        # The number of seconds to wait for the notification to be sent and processed.
        # Default is None
        timeout = None

        # Controls if notifications are sent.
        # Valid values: True or False
        # Default is True.
        send = True

        # Controls if notifications are written to the log.
        # Valid values: True or False
        # Default is True.
        log = True

        # The server to send the pushover request to.
        # Default is api.pushover.net:443.
        server = api.pushover.net:443

        # The endpoint/API to use.
        # Default is /1/messages.json.
        api = /1/messages.json

        #  The API token that is returned when registering the application
        app_token = REPLACE_ME

        # The user key.
        user_key = REPLACE_ME

        # Pushover returns a status code in the range of 400 to 499 when the http request is bad.
        # In this case, WeeWX-Pushover will stop sending requests.
        # (On the assumption that all future requests will have the same error.)
        # An error will be logged every 'client_error_log_frequency' seconds.
        # The default is 3600 seconds.
        client_error_log_frequency = 3600

        # Pushover returns a status code in the range of 500 to 599 when something went wrong on the server.
        # In this case WeeWX-Pushover will wait 'server_error_wait_period' before resuming sending requests.
        # (On the assumption that the server needs some time to be fixed.)
        # The default is 3600 seconds.
        server_error_wait_period = 3600

    # Whether to monitor the loop or archive data.
    # With two sections [[loop]] and [[archive]], both loop and archive data can be monitored.
    [['loop' or 'archive']]
        # Each subsection is the name of WeeWX observation being monitored.
        # These can be any value, but must be unique.
        # For example, aqi_100, aqi_150, outTemp
        [[[REPLACE_ME]]]
            # The WeeWX name.
            # Defaults to the section name.
            # If the section name is not a WeeWX name, this must be set.
            # weewx_name = REPLACE_ME

            # A more human readable 'name' for this observation.
            # Default value is 'empty'/no value.
            # label =

            # The type of notification.
            # Specify one or more.
            [[[[ 'min' or 'max' or 'equal' or 'missing']]]]
                # The value to monitor.
                # A notification is sent when:
                #    the section is 'min' and the observation is less than 'value
                #    the section is 'max' and the observation is greater than 'value
                #    the section is 'equal' and the observation is not equal to 'value
                # Does not need to be set when the section is 'missing'.
                # The value is an integer.
                value = REPLACE_ME

                # The number of times the threshold needs to be reached before sending a notification.
                # The default is 10.
                count = 10

                # The time in seconds to wait before sending another notification.
                # This is used to throttle the number of notifications.
                # The default is 3600 seconds.
                wait_time = 3600

                # Whether to send a notification when the value is back within the threshold.
                # Valid values: True or False
                # Default is True.
                return_notification = True
'''

import http.client
import json
import time
import urllib

from weeutil.weeutil import to_bool, to_int
import user.notify

def format_timestamp(ts, format_str="%Y-%m-%d %H:%M:%S %Z"):
    ''' Format a timestamp for human consumption. '''
    return f"{time.strftime(format_str, time.localtime(ts))}"

class PushOver(user.notify.AbstractNotifier):
    """ Class to perform the pushover call."""
    def __init__(self, logger, notifier_dict):
        super().__init__(logger, notifier_dict)
        self.send = to_bool(notifier_dict.get('send', True))
        self.log = to_bool(notifier_dict.get('log', True))

        self.user_key = notifier_dict.get('user_key', None)
        self.app_token = notifier_dict.get('app_token', None)
        self.server = notifier_dict.get('server', 'api.pushover.net:443')
        self.api = notifier_dict.get('api', '/1/messages.json')

        self.client_error_log_frequency = to_int(notifier_dict.get('client_error_log_frequency', 3600))
        self.server_error_wait_period = to_int(notifier_dict.get('server_error_wait_period', 3600))

        self.client_error_timestamp = 0
        self.client_error_last_logged = 0
        self.server_error_timestamp = 0

    def _logit(self, title, msg):
        self.logger.loginf(self.name, title)
        self.logger.loginf(self.name, msg)

    def throttle_notification(self):
        now = int(time.time())
        if self.client_error_timestamp:
            if abs(now - self.client_error_last_logged) < self.client_error_log_frequency:
                self.logger.logerr(self.name, (f"Fatal error occurred at {format_timestamp(self.client_error_timestamp)}, "
                                               f"Notify skipped."))
                self.client_error_last_logged = now
                return True

        if abs(now - self.server_error_timestamp) < self.server_error_wait_period:
            self.logger.logdbg(self.name, (f"Server error received at {format_timestamp(self.server_error_timestamp)}, "
                                           f"waiting {self.server_error_wait_period} seconds before retrying."))
            return True

        self.server_error_timestamp = 0
        return False

    async def send_notification(self, msg_data):
        self.logger.logdbg(self.name, f"Message data is '{msg_data}'")
        self.logger.logdbg(self.name, f"Server is: '{self.server}' for {msg_data.weewx_name}")
        title = self.build_title(msg_data)
        msg = self.build_message(msg_data)

        if self.log:
            self._logit(title, msg)

        if not self.send:
            return True

        connection = http.client.HTTPSConnection(f"{self.server}")

        connection.request("POST",
                           f"{self.api}",
                           urllib.parse.urlencode({"token": self.app_token,
                                                   "user": self.user_key,
                                                   "message": msg,
                                                   "title": title, }),
                           {"Content-type": "application/x-www-form-urlencoded"})
        response = connection.getresponse()

        return self._check_response(response, msg_data)

    def _check_response(self, response, msg_data):
        ''' Check the response. '''
        now = time.time()
        self.logger.logdbg(self.name, f"Response code is: '{response.code}' for {msg_data.weewx_name}")

        if response.code == 200:
            return True

        self.logger.logerr(self.name, f"Received code '{response.code}' for {msg_data.weewx_name}")
        if response.code >= 400 and response.code < 500:
            self.client_error_timestamp = now
            self.client_error_last_logged = now
        if response.code >= 500 and response.code < 600:
            self.server_error_timestamp = now
        response_body = response.read().decode()
        try:
            response_dict = json.loads(response_body)
            errors = '\n'.join(response_dict['errors'])
            self.logger.logerr(self.name, f"{errors} for {msg_data.weewx_name}")
        except json.JSONDecodeError as exception:
            self.logger.logerr(self.name, f"Unable to parse '{exception.doc}' for {msg_data.weewx_name}.")
            self.logger.logerr(self.name, (f"Error at '{exception.pos}', line: '{exception.lineno}' "
                                           f"column: '{exception.colno}' for {msg_data.weewx_name}"))
        return False
