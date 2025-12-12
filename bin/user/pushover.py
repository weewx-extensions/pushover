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
import logging
import time
import urllib

from weeutil.weeutil import to_bool, to_int
import user.notify

log = logging.getLogger(__name__)

def format_timestamp(ts, format_str="%Y-%m-%d %H:%M:%S %Z"):
    ''' Format a timestamp for human consumption. '''
    return f"{time.strftime(format_str, time.localtime(ts))}"

class PushOver(user.notify.AbstractNotifier):
    """ Class to perform the pushover call."""
    def __init__(self, notifier_dict):
        super().__init__()
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
        log.info(title)
        log.info(msg)

    def throttle_notification(self):
        now = int(time.time())
        if self.client_error_timestamp:
            if abs(now - self.client_error_last_logged) < self.client_error_log_frequency:
                log.error("Fatal error occurred at %s, Notify skipped.", format_timestamp(self.client_error_timestamp))
                self.client_error_last_logged = now
                return True

        if abs(now - self.server_error_timestamp) < self.server_error_wait_period:
            log.debug("Server error received at %s, waiting %s seconds before retrying.",
                      format_timestamp(self.server_error_timestamp),
                      self.server_error_wait_period)
            return True

        self.server_error_timestamp = 0
        return False

    async def send_notification(self, msg_data):
        log.debug("Message data is '%s'", msg_data)
        log.debug("Server is: '%s' for %s", self.server, msg_data.name)
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
        log.debug("Response code is: '%s' for %s", response.code, msg_data.name)

        if response.code == 200:
            return True

        log.error("Received code '%s' for %s", response.code, msg_data.name)
        if response.code >= 400 and response.code < 500:
            self.client_error_timestamp = now
            self.client_error_last_logged = now
        if response.code >= 500 and response.code < 600:
            self.server_error_timestamp = now
        response_body = response.read().decode()
        try:
            response_dict = json.loads(response_body)
            log.error("%s for %s", '\n'.join(response_dict['errors']), msg_data.name)
        except json.JSONDecodeError as exception:
            log.error("Unable to parse '%s' for %s.", exception.doc, msg_data.name)
            log.error("Error at '%s', line: '%s' column: '%s' for %s",
                      exception.pos,
                      exception.lineno,
                      exception.colno,
                      msg_data.name)
        return False
