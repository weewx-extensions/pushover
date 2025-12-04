#
#    Copyright (c) 2023 - 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

'''
Monitor that observation values are within a defined range.
If a value is out of range, send a notification via pushover.net
See, https://pushover.net

Configuration:
[Pushover]

    # Whether the service is enabled or not.
    # Valid values: True or False
    # Default is True.
    # enable = True

    # The server to send the pushover request to.
    # Default is api.pushover.net:443.
    # server = api.pushover.net:443

    # The endpoint/API to use.
    # Default is /1/messages.json.
    # api = /1/messages.json

    app_token = REPLACE_ME
    user_key = REPLACE_ME

    client_error_log_frequency = 3600
    server_error_wait_period = 3600

    # The set of WeeWX observations to monitor.
    # Each subsection is the name of WeeWX observation.
    # For example, outTemp, inTemp, txBatteryStatus, etc
    [[loop or archive]]
        [[[REPLACE_ME]]]
            # A Descriptive name of this observation
            # Default is the WeeWX name.
            #name =

            [[[[ min or max or equal]]]]
                # The time in seconds to wait before sending another notification.
                # This is used to throttle the number of notifications.
                # The default is 3600 seconds.
                #wait_time = 3600

                # The number of times the threshold needs to be reached before sending a notification.
                # The default is 10.
                #count = 10

                # The value to monitor.
                #value = REPLACE_ME
'''

import argparse
import http.client
import json
import logging
import os
import time
import urllib
from concurrent.futures import ThreadPoolExecutor

import configobj

import weewx
from weewx.engine import StdService
from weeutil.weeutil import to_bool, to_int

log = logging.getLogger(__name__)

def format_timestamp(ts, format_str="%Y-%m-%d %H:%M:%S %Z"):
    ''' Format a timestamp for human consumption. '''
    return f"{time.strftime(format_str, time.localtime(ts))}"

class Pushover(StdService):
    """ Manage sending Pushover notifications."""
    def __init__(self, engine, config_dict):
        """Initialize an instance of Pushover"""
        super().__init__(engine, config_dict)

        service_dict = config_dict.get('Pushover', {})

        enable = to_bool(service_dict.get('enable', True))
        if not enable:
            log.info("Pushover is not enabled, exiting")
            return

        push = to_bool(service_dict.get('push', True))
        logit = to_bool(service_dict.get('log', True))

        user_key = service_dict.get('user_key', None)
        app_token = service_dict.get('app_token', None)
        server = service_dict.get('server', 'api.pushover.net:443')
        api = service_dict.get('api', '/1/messages.json')

        client_error_log_frequency = to_int(service_dict.get('client_error_log_frequency', 3600))
        server_error_wait_period = to_int(service_dict.get('server_error_wait_period', 3600))

        count = to_int(service_dict.get('count', 10))
        wait_time = to_int(service_dict.get('wait_time', 3600))
        return_notification = to_bool(service_dict.get('return_notification', True))

        self.loop_observations = {}
        if 'loop' in service_dict:
            default_loop_wait_time = to_int(service_dict['loop'].get('wait_time', wait_time))
            default_loop_return_notification = to_bool(service_dict['loop'].get('return_notification', return_notification))
            for observation in service_dict['loop']:
                self.loop_observations[observation] = self.init_observations(service_dict['loop'][observation],
                                                                             observation,
                                                                             count,
                                                                             default_loop_wait_time,
                                                                             default_loop_return_notification)
        log.info("loop observations: %s", self.loop_observations)

        self.archive_observations = {}
        if 'archive' in service_dict:
            default_archive_wait_time = to_int(service_dict['archive'].get('wait_time', wait_time))
            default_archive_return_notification = to_bool(service_dict['archive'].get('return_notification', return_notification))
            for observation in service_dict['archive']:
                self.archive_observations[observation] = self.init_observations(service_dict['archive'][observation],
                                                                                observation,
                                                                                count,
                                                                                default_archive_wait_time,
                                                                                default_archive_return_notification)
        log.info("archive observations: %s", self.archive_observations)

        self.missing_observations = {}

        self.pusher = Pusher(server, api, app_token, user_key, client_error_log_frequency, server_error_wait_period, push, logit)

        self.executor = ThreadPoolExecutor(max_workers=5)

        if self.archive_observations:
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        if self.loop_observations:
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

    def init_observations(self, config, observation_name, count, wait_time, return_notification):
        ''' Initialize the observation configruation. '''
        observation = {}
        observation['name'] = config.get('name', observation_name)
        observation['weewx_name'] = config.get('weewx_name', observation_name)
        observation['label'] = config.get('label', '')
        if observation['label']:
            observation['label'] = ' (' + observation['label'] + ')'

        for value_type in ['min', 'max', 'equal', 'missing']:
            if value_type in config:
                observation[value_type] = {}
                if value_type != 'missing':
                    observation[value_type]['value'] = int(config[value_type]['value'])
                else:
                    observation['returned'] = {}
                observation[value_type]['count'] = int(config[value_type].get('count', count))
                observation[value_type]['wait_time'] = to_int(config[value_type].get('wait_time', wait_time))
                observation[value_type]['return_notification'] = to_bool(config[value_type].get('return_notification',
                                                                                                return_notification))
                observation[value_type]['last_sent_timestamp'] = 0
                observation[value_type]['counter'] = 0

        return observation

    def check_min_value(self, name, label, observation_detail, value):
        ''' Check if an observation is less than a desired value.
            Send a notification if time and cound thresholds have been met. '''
        now = int(time.time())
        log.debug("  Min check if %s is less than %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta Min is %s and threshold is %s for %s%s", time_delta, observation_detail['wait_time'], name, label)
        log.debug("    Running count Min is %s and threshold is %s for %s%s",
                  observation_detail['counter'],
                  observation_detail['count'],
                  name,
                  label)

        msg = ''
        if value < observation_detail['value']:
            if 'threshold_passed' not in observation_detail:
                observation_detail['threshold_passed'] = {}
                observation_detail['threshold_passed']['timestamp'] = now
                observation_detail['threshold_passed']['notification_count'] = 0

            observation_detail['counter'] += 1
            if time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    observation_detail['threshold_passed']['notification_count'] += 1
                    msg = (f"At {format_timestamp(observation_detail['threshold_passed']['timestamp'])} {name}{label} "
                           f"went below threshold of {observation_detail['value']}. Current value is {value}.\n")
        else:
            if 'threshold_passed' in observation_detail:
                if observation_detail['threshold_passed']['notification_count'] > 0:
                    if observation_detail['return_notification']:
                        msg = (f"{name}{label} under Min threshold at "
                               f"{format_timestamp(observation_detail['threshold_passed']['timestamp'])} "
                               f"is within threshold with value {value}, "
                               f"{observation_detail['threshold_passed']['notification_count']} notifications sent.\n")
                    else:
                        log.debug("    Notification not requested for %s%s going under Min threshold at %s and count of %s.",
                                  name,
                                  label,
                                  format_timestamp(observation_detail['threshold_passed']['timestamp']),
                                  observation_detail['counter'])
                else:
                    log.info("No notifcations had been sent for %s%s going under Min threshold at %s and count of %s.",
                             name,
                             label,
                             format_timestamp(observation_detail['threshold_passed']['timestamp']),
                             observation_detail['counter'])

                observation_detail['counter'] = 0
                # Setting to 1 is a hack, this allows the time threshold to be met
                # But does not short circuit checking the count threshold
                observation_detail['last_sent_timestamp'] = 1

                del observation_detail['threshold_passed']

        return msg

    def check_max_value(self, name, label, observation_detail, value):
        ''' Check if an observation is greater than a desired value.
            Send a notification if time and cound thresholds have been met. '''
        now = int(time.time())
        log.debug("  Max check if %s is greater than %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta Max is %s and threshold is %s for %s%s", time_delta, observation_detail['wait_time'], name, label)
        log.debug("    Running count Max is %s and threshold is %s for %s%s",
                  observation_detail['counter'],
                  observation_detail['count'],
                  name,
                  label)

        msg = ''
        if value > observation_detail['value']:
            if 'threshold_passed' not in observation_detail:
                observation_detail['threshold_passed'] = {}
                observation_detail['threshold_passed']['timestamp'] = now
                observation_detail['threshold_passed']['notification_count'] = 0

            observation_detail['counter'] += 1
            if time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    observation_detail['threshold_passed']['notification_count'] += 1
                    msg = (f"At {format_timestamp(observation_detail['threshold_passed']['timestamp'])} {name}{label} "
                           f"went above threshold of {observation_detail['value']}. Current value is {value}.\n")
        else:
            if 'threshold_passed' in observation_detail:
                if observation_detail['threshold_passed']['notification_count'] > 0:
                    if observation_detail['return_notification']:
                        msg = (f"{name}{label} over Max threshold at "
                               f"{format_timestamp(observation_detail['threshold_passed']['timestamp'])} "
                               f"is within threshold with value {value}, "
                               f"{observation_detail['threshold_passed']['notification_count']} notifications sent.\n")
                    else:
                        log.debug("    Notification not requested for %s%s going over Max threshold at %s and count of %s.",
                                  name,
                                  label,
                                  format_timestamp(observation_detail['threshold_passed']['timestamp']),
                                  observation_detail['counter'])
                else:
                    log.info("No notifcations had been sent for %s%s going over Max threshold at %s and count of %s.",
                             name,
                             label,
                             format_timestamp(observation_detail['threshold_passed']['timestamp']),
                             observation_detail['counter'])

                observation_detail['counter'] = 0
                # Setting to 1 is a hack, this allows the time threshold to be met
                # But does not short circuit checking the count threshold
                observation_detail['last_sent_timestamp'] = 1

                del observation_detail['threshold_passed']

        return msg

    def check_equal_value(self, name, label, observation_detail, value):
        ''' Check if an observation is not equal to desired value.
            Send a notification if time and cound thresholds have been met. '''
        now = int(time.time())
        log.debug("  Equal check if %s is equal to %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta Equal is %s and threshold is %s for %s%s",
                  time_delta,
                  observation_detail['wait_time'],
                  name,
                  label)
        log.debug("    Running count Equal is %s and threshold is %s for %s%s",
                  observation_detail['counter'],
                  observation_detail['count'],
                  name,
                  label)

        msg = ''
        if value != observation_detail['value']:
            if 'threshold_passed' not in observation_detail:
                observation_detail['threshold_passed'] = {}
                observation_detail['threshold_passed']['timestamp'] = now
                observation_detail['threshold_passed']['notification_count'] = 0

            observation_detail['counter'] += 1
            if time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    observation_detail['threshold_passed']['notification_count'] += 1
                    msg = (f"At {format_timestamp(observation_detail['threshold_passed']['timestamp'])} {name}{label} "
                           f"is no longer equal to threshold of {observation_detail['value']}. Current value is {value}.\n")
        else:
            if 'threshold_passed' in observation_detail:
                if observation_detail['threshold_passed']['notification_count'] > 0:
                    if observation_detail['return_notification']:
                        msg = (f"{name}{label} Not Equal at {format_timestamp(observation_detail['threshold_passed']['timestamp'])} "
                               f"is within threshold with value {value}, "
                               f"{observation_detail['threshold_passed']['notification_count']} notifications sent.\n")
                    else:
                        log.debug("    Notification not requested for %s%s being Not Equal at %s and count of %s.",
                                  name,
                                  label,
                                  format_timestamp(observation_detail['threshold_passed']['timestamp']),
                                  observation_detail['counter'])
                else:
                    log.info("No notifcations had been sent for %s%s being Not Equal at %s and count of %s.",
                             name,
                             label,
                             format_timestamp(observation_detail['threshold_passed']['timestamp']),
                             observation_detail['counter'])

                observation_detail['counter'] = 0
                # Setting to 1 is a hack, this allows the time threshold to be met
                # But does not short circuit checking the count threshold
                observation_detail['last_sent_timestamp'] = 1

                del observation_detail['threshold_passed']

        return msg

    def check_missing_value(self, observation, name, label, observation_detail):
        ''' Check if a notification should be sent for a missing value.'''
        log.debug("  Processing missing for %s%s", name, label)
        now = int(time.time())
        time_delta = now - observation_detail['last_sent_timestamp']
        log.debug("    Time delta is %s, threshold is %s, and last sent is %s for %s%s",
                  time_delta,
                  observation_detail['wait_time'],
                  observation_detail['last_sent_timestamp'],
                  observation,
                  label)
        log.debug("    Running count is %s and threshold is %s for %s%s",
                  observation_detail['counter'],
                  observation_detail['count'],
                  observation,
                  label)

        if observation not in self.missing_observations:
            self.missing_observations[observation] = {}
            self.missing_observations[observation]['missing_time'] = now
            self.missing_observations[observation]['notification_count'] = 0

        observation_detail['counter'] += 1
        msg = ''
        if time_delta >= observation_detail['wait_time']:
            if observation_detail['counter'] >= observation_detail['count'] or observation_detail['last_sent_timestamp'] == 0:
                self.missing_observations[observation]['notification_count'] += 1
                msg = (f"{name}{label} missing at {format_timestamp(self.missing_observations[observation]['missing_time'])}, "
                       f"{self.missing_observations[observation]['notification_count']} notifications sent.\n")
        return msg

    def check_value_returned(self, observation, name, label, observation_detail, value):
        ''' Check if a notification should be sent when a missing value has returned. '''
        # ToDo: I think this needs work - think it is closer
        log.debug("  Processing returned value for observation %s%s", name, label)
        now = int(time.time())
        time_delta = now - observation_detail['last_sent_timestamp']
        log.debug("    Time delta is %s, threshold is %s, and last sent is %s for %s%s",
                  time_delta,
                  observation_detail['wait_time'],
                  observation_detail['last_sent_timestamp'],
                  observation, label)
        log.debug("    Running count is %s and threshold is %s for %s%s",
                  observation_detail['counter'],
                  observation_detail['count'],
                  observation,
                  label)
        msg = ''
        if observation in self.missing_observations:
            if self.missing_observations[observation]['notification_count'] > 0:
                if observation_detail['return_notification']:
                    msg = (f"{name}{label} missing at {format_timestamp(self.missing_observations[observation]['missing_time'])} "
                           f"returned with value {value}, "
                           f"{self.missing_observations[observation]['notification_count']} notification sent.\n")
                else:
                    log.debug("    Notification not requested for %s%s gone missing at %s and count of %s.",
                              name,
                              label,
                              format_timestamp(self.missing_observations[observation]['missing_time']),
                              observation_detail['counter'])
            else:
                log.info("No notifcations had been sent for returning %s%s gone missing at %s and count of %s.",
                         name,
                         label,
                         format_timestamp(self.missing_observations[observation]['missing_time']), observation_detail['counter'])
            observation_detail['counter'] = 0
            # Setting to 1 is a hack, this allows the time threshold to be met
            # But does not short circuit checking the count threshold
            observation_detail['last_sent_timestamp'] = 1

            del self.missing_observations[observation]

        # Setting to 1 is a hack, this allows the time threshold to be met
        # But does not short circuit checking the count threshold
        # In otherwords, a value has been find since WeeWX started....
        if observation_detail['last_sent_timestamp'] == 0:
            observation_detail['last_sent_timestamp'] = 1

        return msg

    def _process_data(self, data, observations):
        # log.debug("Processing record: %s", data)
        msgs = {}
        for obs, observation_detail in observations.items():
            observation = observation_detail['weewx_name']
            title = None

            if observation in data and data[observation] is not None:
                log.debug("Processing observation: %s%s", observation, observation_detail['label'])
                # This means that if an observation 'goes missing', it needs a value that is not None to be marked as 'back'
                if observation_detail.get('missing', None):
                    # ToDo: I think it needs to be different than msgs['missing']
                    msgs['returned'] = self.check_value_returned(observation,
                                                                 observation_detail['name'],
                                                                 observation_detail['label'],
                                                                 observation_detail['missing'],
                                                                 data[observation])
                    if msgs['returned']:
                        title = f"Unexpected value for {observation}."
                        # self.executor.submit(self._push_notification, event.packet)
                        self.pusher.push_notification(obs, observation_detail, title, msgs)
                        msgs = {}
                        title = ''

                if observation_detail.get('min', None):
                    msgs['min'] = self.check_min_value(observation_detail['name'],
                                                       observation_detail['label'],
                                                       observation_detail['min'],
                                                       data[observation])
                    if msgs['min']:
                        title = f"Unexpected value for {observation}."
                        # self.executor.submit(self._push_notification, event.packet)
                        self.pusher.push_notification(obs, observation_detail, title, msgs)
                        msgs = {}
                        title = ''

                if observation_detail.get('max', None):
                    msgs['max'] = self.check_max_value(observation_detail['name'],
                                                       observation_detail['label'],
                                                       observation_detail['max'],
                                                       data[observation])
                    if msgs['max']:
                        title = f"Unexpected value for {observation}."
                        # self.executor.submit(self._push_notification, event.packet)
                        self.pusher.push_notification(obs, observation_detail, title, msgs)
                        msgs = {}
                        title = ''

                if observation_detail.get('equal', None):
                    msgs['equal'] = self.check_equal_value(observation_detail['name'],
                                                           observation_detail['label'],
                                                           observation_detail['equal'],
                                                           data[observation])
                    if msgs['equal']:
                        title = f"Unexpected value for {observation}."
                        # self.executor.submit(self._push_notification, event.packet)
                        self.pusher.push_notification(obs, observation_detail, title, msgs)
                        msgs = {}
                        title = ''

            if observation not in data and observation_detail.get('missing', None):
                msgs['missing'] = self.check_missing_value(observation,
                                                           observation_detail['name'],
                                                           observation_detail['label'],
                                                           observation_detail['missing'])
                if msgs['missing']:
                    title = f"Unexpected value for {observation}."
                    # self.executor.submit(self._push_notification, event.packet)
                    self.pusher.push_notification(obs, observation_detail, title, msgs)
                    msgs = {}
                    title = ''

    def new_archive_record(self, event):
        """ Handle the new archive record event. """
        if not self.pusher.throttle_notification():
            self._process_data(event.record, self.archive_observations)

    def new_loop_packet(self, event):
        """ Handle the new loop packet event. """
        if not self.pusher.throttle_notification():
            self._process_data(event.packet, self.loop_observations)

    def shutDown(self):
        """Run when an engine shutdown is requested."""
        self.executor.shutdown(wait=False)

class Pusher():
    """ Class to perform the pushover call."""
    def __init__(self, server, api, app_token, user_key, client_error_log_frequency, server_error_wait_period, push, logit):
        self.server = server
        self.api = api
        self.app_token = app_token
        self.user_key = user_key
        self.client_error_log_frequency = client_error_log_frequency
        self.server_error_wait_period = server_error_wait_period
        self.push = push
        self.log = logit

        self.client_error_timestamp = 0
        self.client_error_last_logged = 0
        self.server_error_timestamp = 0

    def _logit(self, title, msgs):
        msg = ''
        for _, value in msgs.items():
            if value:
                msg += value
        log.info(title)
        log.info(msg)

    def throttle_notification(self):
        ''' Check if the call should be performed or throttled.'''
        now = int(time.time())
        if self.client_error_timestamp:
            if abs(now - self.client_error_last_logged) < self.client_error_log_frequency:
                log.error("Fatal error occurred at %s, Pushover skipped.", format_timestamp(self.client_error_timestamp))
                self.client_error_last_logged = now
                return True

        if abs(now - self.server_error_timestamp) < self.server_error_wait_period:
            log.debug("Server error received at %s, waiting %s seconds before retrying.",
                      format_timestamp(self.server_error_timestamp),
                      self.server_error_wait_period)
            return True

        self.server_error_timestamp = 0
        return False

    def push_notification(self, obs, observation_detail, title, msgs):
        ''' Perform the call.'''
        now = time.time()
        msg = ''
        for _, value in msgs.items():
            if value:
                msg += value
        log.debug("Title is '%s' for %s", title, obs)
        log.debug("Message is '%s' for %s", msg, obs)
        log.debug("Server is: '%s' for %s", self.server, obs)

        if self.log:
            self._logit(title, msgs)

        if self.push:
            connection = http.client.HTTPSConnection(f"{self.server}")

            connection.request("POST",
                            f"{self.api}",
                            urllib.parse.urlencode({"token": self.app_token,
                                                    "user": self.user_key,
                                                    "message": msg,
                                                    "title": title, }),
                            {"Content-type": "application/x-www-form-urlencoded"})
            response = connection.getresponse()

            self.check_response(response, obs, msgs, observation_detail)
        else:
            for key, value in msgs.items():
                if value:
                    observation_detail[key]['last_sent_timestamp'] = now
                    observation_detail[key]['counter'] = 0

    def check_response(self, response, obs, msgs, observation_detail):
        ''' Check the response. '''
        now = time.time()
        log.debug("Response code is: '%s' for %s", response.code, obs)

        if response.code == 200:
            for key, value in msgs.items():
                if value:
                    observation_detail[key]['last_sent_timestamp'] = now
                    observation_detail[key]['counter'] = 0

        else:
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
                log.error("Error at '%s', line: '%s' column: '%s' for %s",
                          exception.pos, exception.lineno, exception.colno, obs)

def main():  # pragma no cover
    """ The main routine. """
    min_config_dict = {
        'Station': {
            'altitude': [0, 'foot'],
            'latitude': 0,
            'station_type': 'Simulator',
            'longitude': 0
        },
        'Simulator': {
            'driver': 'weewx.drivers.simulator',
        },
        'Engine': {
            'Services': {}
        }
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("--conf",
                        required=True,
                        help="The WeeWX configuration file. Typically weewx.conf.")
    options = parser.parse_args()

    config_path = os.path.abspath(options.conf)
    config_dict = configobj.ConfigObj(config_path, file_error=True)

    engine = weewx.engine.DummyEngine(min_config_dict)

    packet = {'dateTime': int(time.time()),
              'mon_extraTemp6': 6,
              }

    # ToDo: Make enable an option
    config_dict['Pushover']['enable'] = True

    pushover = Pushover(engine, config_dict)

    event = weewx.Event(weewx.NEW_LOOP_PACKET, packet=packet)

    pushover.new_loop_packet(event)

    event = weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=packet)
    pushover.new_archive_record(event)

    packet = {'dateTime': int(time.time()),
              'mon_extraTemp6': 6,
              'mon_extraTemp1': 1,
              }
    event = weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=packet)
    pushover.new_archive_record(event)

    pushover.shutDown()

if __name__ == '__main__':
    main()
