#
#    Copyright (c) 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
'''
Send a notification via pushover, pushover.net
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
        self.logger.loginf(title)
        self.logger.loginf(msg)

    def throttle_notification(self):
        now = int(time.time())
        if self.client_error_timestamp:
            if abs(now - self.client_error_last_logged) < self.client_error_log_frequency:
                self.logger.logerr(f"Fatal error occurred at {format_timestamp(self.client_error_timestamp)}, Notify skipped.")
                self.client_error_last_logged = now
                return True

        if abs(now - self.server_error_timestamp) < self.server_error_wait_period:
            self.logger.logdbg((f"Server error received at {format_timestamp(self.server_error_timestamp)}, "
                                f"waiting {self.server_error_wait_period} seconds before retrying."))
            return True

        self.server_error_timestamp = 0
        return False

    async def send_notification(self, msg_data):
        self.logger.logdbg(f"Message data is '{msg_data}'")
        self.logger.logdbg(f"Server is: '{self.server}' for {msg_data.name}")
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
        self.logger.logdbg(f"Response code is: '{response.code}' for {msg_data.name}")

        if response.code == 200:
            return True

        self.logger.logerr(f"Received code '{response.code}' for {msg_data.name}")
        if response.code >= 400 and response.code < 500:
            self.client_error_timestamp = now
            self.client_error_last_logged = now
        if response.code >= 500 and response.code < 600:
            self.server_error_timestamp = now
        response_body = response.read().decode()
        try:
            response_dict = json.loads(response_body)
            errors = '\n'.join(response_dict['errors'])
            self.logger.logerr(f"{errors} for {msg_data.name}")
        except json.JSONDecodeError as exception:
            self.logger.logerr(f"Unable to parse '{exception.doc}' for {msg_data.name}.")
            self.logger.logerr((f"Error at '{exception.pos}', line: '{exception.lineno}' "
                                f"column: '{exception.colno}' for {msg_data.name}"))
        return False
