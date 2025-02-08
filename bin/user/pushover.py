#
#    Copyright (c) 2023 - 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=fixme
# pylint: disable=line-too-long
# ToDo: find a better way to handle pylint errors

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

        self.push = to_bool(service_dict.get('push', True))
        self.log = to_bool(service_dict.get('log', True))

        self.user_key = service_dict.get('user_key', None)
        self.app_token = service_dict.get('app_token', None)
        self.server = service_dict.get('server', 'api.pushover.net:443')
        self.api = service_dict.get('api', '/1/messages.json')

        self.client_error_log_frequency = to_int(service_dict.get('client_error_log_frequency', 3600))
        self.server_error_wait_period = to_int(service_dict.get('server_error_wait_period', 3600))

        count = to_int(service_dict.get('count', 10))
        wait_time = to_int(service_dict.get('wait_time', 3600))

        self.loop_observations = {}
        if 'loop' in service_dict:
            default_loop_wait_time = to_int(service_dict['loop'].get('wait_time', wait_time))
            for observation in service_dict['loop']:
                self.loop_observations[observation] = self.init_observations(service_dict['loop'][observation], observation, count, default_loop_wait_time)
        log.info("loop observations: %s", self.loop_observations)

        self.archive_observations = {}
        if 'archive' in service_dict:
            default_archive_wait_time = to_int(service_dict['archive'].get('wait_time', wait_time))
            for observation in service_dict['archive']:
                self.archive_observations[observation] = self.init_observations(service_dict['archive'][observation], observation, count, default_archive_wait_time)
        log.info("archive observations: %s", self.archive_observations)

        self.client_error_timestamp = 0
        self.client_error_last_logged = 0
        self.server_error_timestamp = 0
        self.missing_observations = {}

        self.executor = ThreadPoolExecutor(max_workers=5)

        if self.archive_observations:
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        if self.loop_observations:
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

    def init_observations(self, config, observation_name, count, wait_time):
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
                observation[value_type]['last_sent_timestamp'] = 0
                observation[value_type]['counter'] = 0

        return observation

    def _logit(self, title, msgs):
        msg = ''
        for _, value in msgs.items():
            if value:
                msg += value
        log.info(title)
        log.info(msg)

    def _push_notification(self, obs, observation_detail, title, msgs):
        msg = ''
        for _, value in msgs.items():
            if value:
                msg += value
        log.debug("Title is '%s' for %s", title, obs)
        log.debug("Message is '%s' for %s", msg, obs)
        log.debug("Server is: '%s' for %s", self.server, obs)
        connection = http.client.HTTPSConnection(f"{self.server}")

        connection.request("POST",
                           f"{self.api}",
                           urllib.parse.urlencode({
                               "token": self.app_token,
                               "user": self.user_key,
                               "message": msg,
                               "title": title,                               
                               }),
                            { "Content-type": "application/x-www-form-urlencoded" })
        response = connection.getresponse()
        now = int(time.time())
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

    def check_min_value(self, name, label, observation_detail, value):
        ''' Check if an observation is less than a desired value.
            Send a notification if time and cound thresholds have been met. '''
        now = int(time.time())
        log.debug("  Min check if %s is less than %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta is %s and threshold is %s for %s%s", time_delta, observation_detail['wait_time'], name, label)
        log.debug("    Running count is %s and threshold is %s for %s%s", observation_detail['counter'], observation_detail['count'], name, label)

        msg = ''
        if value < observation_detail['value']:
            observation_detail['counter'] += 1
            if  time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    msg = f"{name}{label} value {value} is less than {observation_detail['value']}.\n"

        return msg

    def check_max_value(self, name, label, observation_detail, value):
        ''' Check if an observation is greater than a desired value.
            Send a notification if time and cound thresholds have been met. '''
        now = int(time.time())
        log.debug("  Max check if %s is greater than %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta is %s and threshold is %s for %s%s", time_delta, observation_detail['wait_time'], name, label)
        log.debug("    Running count is %s and threshold is %s for %s%s", observation_detail['counter'], observation_detail['count'], name, label)

        msg = ''
        if value > observation_detail['value']:
            observation_detail['counter'] += 1
            if  time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    msg = f"{name}{label} value {value} is greater than {observation_detail['value']}.\n"

        return msg

    def check_equal_value(self, name, label, observation_detail, value):
        ''' Check if an observation is not equal to desired value.
            Send a notification if time and cound thresholds have been met. '''
        now = int(time.time())
        log.debug("  Equal check if %s is equal to %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta is %s and threshold is %s for %s%s", time_delta, observation_detail['wait_time'], name, label)
        log.debug("    Running count is %s and threshold is %s for %s%s", observation_detail['counter'], observation_detail['count'], name, label)

        msg = ''
        if value != observation_detail['value']:
            observation_detail['counter'] += 1
            if  time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    msg = f"{name}{label} value {value} is not equal to {observation_detail['value']}.\n"

        return msg

    def check_missing_value(self, observation, name, label, observation_detail):
        ''' Check if a notification should be sent for a missing value.'''
        log.debug("  Processing missing for %s%s", name, label)
        now = int(time.time())
        time_delta = now - observation_detail['last_sent_timestamp']
        log.debug("    Time delta is %s, threshold is %s, and last sent is %s for %s%s", time_delta, observation_detail['wait_time'], observation_detail['last_sent_timestamp'], observation, label)
        log.debug("    Running count is %s and threshold is %s for %s%s", observation_detail['counter'], observation_detail['count'], observation, label)

        if observation not in self.missing_observations:
            self.missing_observations[observation] = {}
            self.missing_observations[observation]['missing_time'] = now
            self.missing_observations[observation]['notification_count'] = 0

        observation_detail['counter'] += 1
        msg = ''
        if  time_delta >= observation_detail['wait_time']:
            if observation_detail['counter'] >= observation_detail['count'] or observation_detail['last_sent_timestamp'] == 0:
                msg = f"{name}{label} is missing with a count of {observation_detail['counter']}.\n"
                self.missing_observations[observation]['notification_count'] += 1

        return msg

    def check_value_returned(self, observation, name, label, observation_detail, value):
        ''' Check if a notification should be sent when a missing value has returned. '''
        # ToDo: I think this needs work - think it is closer
        log.debug("  Processing returned value for observation %s%s", name, label)
        now = int(time.time())
        time_delta = now - observation_detail['last_sent_timestamp']
        log.debug("    Time delta is %s, threshold is %s, and last sent is %s for %s%s", time_delta, observation_detail['wait_time'], observation_detail['last_sent_timestamp'], observation, label)
        log.debug("    Running count is %s and threshold is %s for %s%s", observation_detail['counter'], observation_detail['count'], observation, label)
        msg = ''
        if observation in self.missing_observations:
            if self.missing_observations[observation]['notification_count'] > 0:
                msg = f"{name}{label} returned at {self.missing_observations[observation]['missing_time']} after missing for {observation_detail['counter']} with value {value}.\n"
            else:
                log.debug("    No notifcations had been sent for returning %s%s gone missing at %s and count of %s.", name, label,self.missing_observations[observation]['missing_time'], observation_detail['counter'])
            observation_detail['counter'] = 0
            # Setting to 1 is a hack, this allows the time threshold to be met
            # But does not short circuit checking the count threshold
            observation_detail['last_sent_timestamp'] = 1

            del self.missing_observations[observation]
        return msg

    def _process_data(self, data, observations):
        #log.debug("Processing record: %s", data)
        msgs = {}
        now = int(time.time())
        for obs, observation_detail in observations.items():
            observation = observation_detail['weewx_name']
            title = None

            if observation in data and data[observation]:
                log.debug("Processing observation: %s%s", observation, observation_detail['label'])
                # This means that if an observation 'goes missing', it needs a value that is not None to be marked as 'back'
                if observation_detail.get('missing', None):
                    # ToDo: I think it needs to be different than msgs['missing']
                    msgs['returned'] = self.check_value_returned(observation, observation_detail['name'], observation_detail['label'], observation_detail['missing'], data[observation])
                    if msgs['returned']:
                        title = f"Unexpected value for {observation}."
                if observation_detail.get('min', None):
                    msgs['min'] = self.check_min_value(observation_detail['name'], observation_detail['label'], observation_detail['min'], data[observation])
                    if msgs['min']:
                        title = f"Unexpected value for {observation}."
                if observation_detail.get('max', None):
                    msgs['max'] = self.check_max_value(observation_detail['name'], observation_detail['label'], observation_detail['max'], data[observation])
                    if msgs['max']:
                        title = f"Unexpected value for {observation}."
                if observation_detail.get('equal', None):
                    msgs['equal'] = self.check_equal_value(observation_detail['name'], observation_detail['label'], observation_detail['equal'], data[observation])
                    if msgs['equal']:
                        title = f"Unexpected value for {observation}."

            if observation not in data and observation_detail.get('missing', None):
                msgs['missing'] = self.check_missing_value(observation, observation_detail['name'], observation_detail['label'], observation_detail['missing'])
                if msgs['missing']:
                    title = f"Unexpected value for {observation}."

            if title:
                if self.log:
                    self._logit(title, msgs)
                if self.push:
                    #self.executor.submit(self._push_notification, event.packet)
                    self._push_notification(obs, observation_detail, title, msgs)
                else:
                    for key, value in msgs.items():
                        if value:
                            observation_detail[key]['last_sent_timestamp'] = now
                            observation_detail[key]['counter'] = 0

    def new_archive_record(self, event):
        """ Handle the new archive record event. """
        now = int(time.time())
        if self.client_error_timestamp:
            if abs(now - self.client_error_last_logged) < self.client_error_log_frequency:
                log.error("Fatal error occurred at %s, Pushover skipped.", self.client_error_timestamp)
                self.client_error_last_logged = now
                return

        if abs(now - self.server_error_timestamp) < self.server_error_wait_period:
            log.debug("Server error received at %s, waiting %s seconds before retrying.",
                      self.server_error_timestamp,
                      self.server_error_wait_period)
            return
        self.server_error_timestamp = 0

        self._process_data(event.record, self.archive_observations)

    def new_loop_packet(self, event):
        """ Handle the new loop packet event. """
        now = int(time.time())
        if self.client_error_timestamp:
            if abs(now - self.client_error_last_logged) < self.client_error_log_frequency:
                log.error("Fatal error occurred at %s, Pushover skipped.", self.client_error_timestamp)
                self.client_error_last_logged = now
                return

        if abs(now - self.server_error_timestamp) < self.server_error_wait_period:
            log.debug("Server error received at %s, waiting %s seconds before retrying.",
                      self.server_error_timestamp,
                      self.server_error_wait_period)
            return
        self.server_error_timestamp = 0

        self._process_data(event.packet, self.loop_observations)

    def shutDown(self): # need to override parent - pylint: disable=invalid-name
        """Run when an engine shutdown is requested."""
        self.executor.shutdown(wait=False)

def main():
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
