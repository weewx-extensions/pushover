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

    def build_message(self, threshold_type, msg_data):
        """ Build a message based on threshold status."""
        msg_template = {
            'equal': {
                'outside': ("At {date_time} {name}{label} is no longer equal to threshold of {threshold_value}. "
                            "Current value is {current_value}. {notifications_sent} sent.\n"),
                'within': ("{name}{label} Not Equal at {date_time} is within threshold with value {current_value}, "
                           "{notifications_sent} notifications sent.\n"),
            },
            'max': {
                'outside': ("At {date_time} {name}{label} went above threshold of {threshold_value}. "
                            "Current value is {current_value}. {notifications_sent} sent.\n"),
                'within': ("{name}{label} over Max threshold at {date_time} is within threshold with value {current_value}, "
                           "{notifications_sent} notifications sent.\n"),
            },
            'min': {
                'outside': ("At {date_time} {name}{label} went below threshold of {threshold_value}. "
                            "Current value is {current_value}. {notifications_sent} sent.\n"),
                'within': ("{name}{label} over Min threshold at {date_time} is within threshold with value {current_value}, "
                           "{notifications_sent} notifications sent.\n"),
            },
        }

        msg_missing_template = "{name}{label} missing at {date_time}, {notifications_sent} notifications sent.\n"

        msg_returned_template = ("{name}{label} missing at {date_time} returned with value {current_value}, "
                                 "{notifications_sent} notification sent.\n")

        if threshold_type == 'missing':
            return msg_missing_template.format(name=msg_data.name,
                                               label=msg_data.label,
                                               date_time=format_timestamp(msg_data.date_time),
                                               notifications_sent=msg_data.notifications_sent)

        if threshold_type == 'returned':
            return msg_returned_template.format(name=msg_data.name,
                                                label=msg_data.label,
                                                date_time=format_timestamp(msg_data.date_time),
                                                current_value=msg_data.current_value,
                                                notifications_sent=msg_data.notifications_sent)

        return msg_template[threshold_type][msg_data.type].format(date_time=format_timestamp(msg_data.date_time),
                                                                     name=msg_data.name,
                                                                     label=msg_data.label,
                                                                     threshold_value=msg_data.threshold_value,
                                                                     current_value=msg_data.current_value,
                                                                     notifications_sent=msg_data.notifications_sent
                                                                     )

    def throttle_notification(self):
        ''' Check if the call should be performed or throttled.'''
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

    def send_notification(self, threshold_type, msg_data):
        ''' Perform the call.'''
        log.debug("Message data is '%s'", msg_data)
        log.debug("Server is: '%s' for %s", self.server, msg_data.name)
        title = f"Unexpected value for {msg_data.name}."
        msg = self.build_message(threshold_type, msg_data)

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

        return self.check_response(response, msg_data.name)

    def check_response(self, response, obs):
        ''' Check the response. '''
        now = time.time()
        log.debug("Response code is: '%s' for %s", response.code, obs)

        if response.code == 200:
            return True

        log.error("Received code '%s' for %s", response.code, obs)
        if response.code >= 400 and response.code < 500:
            self.client_error_timestamp = now
            self.client_error_last_logged = now
        if response.code >= 500 and response.code < 600:
            self.server_error_timestamp = now
        response_body = response.read().decode()
        try:
            response_dict = json.loads(response_body)
            log.error("%s for %s", '\n'.join(response_dict['errors']), obs)
        except json.JSONDecodeError as exception:
            log.error("Unable to parse '%s' for %s.", exception.doc, obs)
            log.error("Error at '%s', line: '%s' column: '%s' for %s", exception.pos, exception.lineno, exception.colno, obs)
        return False
