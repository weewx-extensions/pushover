#
#    Copyright (c) 2023 - 2025 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

'''
Monitor that observation values are within a defined range.
If a value is out of range, send a notification.

Configuration:
[Notify]
    # Whether the service is enabled or not.
    # Valid values: True or False
    # Default is True.
    enable = True

[[notifier]]
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

import argparse
import asyncio
import logging
import os
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

import configobj

import weewx
from weewx.engine import StdService
import weeutil
from weeutil.weeutil import to_bool, to_int

log = logging.getLogger(__name__)

def format_timestamp(ts, format_str="%Y-%m-%d %H:%M:%S %Z"):
    ''' Format a timestamp for human consumption. '''
    return f"{time.strftime(format_str, time.localtime(ts))}"

class Notify(StdService):
    """ Manage sending notifications."""
    def __init__(self, engine, config_dict):
        """Initialize an instance of Notify"""
        super().__init__(engine, config_dict)

        self.notifier_class_name = 'user.pushover.PushOver'
        service_dict = config_dict.get('Notify', {})

        enable = to_bool(service_dict.get('enable', True))
        if not enable:
            log.info("Notify is not enabled, exiting")
            return

        notifier_dict = service_dict.get('notifier', {})

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

        notifier_class = weeutil.weeutil.get_object(self.notifier_class_name)
        self.notifier = notifier_class(notifier_dict)

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
        result = None
        now = int(time.time())
        result2 = {
            'threshold_type': 'min',
            'threshold_value': observation_detail['value'],
            'name': name,
            'label': label,
            'current_value': value,
        }
        log.debug("  Min check if %s is less than %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta Min is %s and threshold is %s for %s%s", time_delta, observation_detail['wait_time'], name, label)
        log.debug("    Running count Min is %s and threshold is %s for %s%s",
                  observation_detail['counter'],
                  observation_detail['count'],
                  name,
                  label)

        if value < observation_detail['value']:
            if observation_detail['counter'] == 0:
                observation_detail['threshold_passed'] = {}
                observation_detail['threshold_passed']['timestamp'] = now
                observation_detail['threshold_passed']['notification_count'] = 0

            observation_detail['counter'] += 1
            if time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    observation_detail['threshold_passed']['notification_count'] += 1
                    result2['type'] = 'outside'
                    result2['notifications_sent'] = observation_detail['threshold_passed']['notification_count']
                    result2['date_time'] = observation_detail['threshold_passed']['timestamp']
                    result = result2
        else:
            if observation_detail['counter'] > 0:
                if observation_detail['threshold_passed']['notification_count'] > 0:
                    if observation_detail['return_notification']:
                        result2['type'] = 'within'
                        result2['notifications_sent'] = observation_detail['threshold_passed']['notification_count']
                        result2['date_time'] = observation_detail['threshold_passed']['timestamp']
                        result = result2
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

        if result:
            return namedtuple('Result', result.keys())(**result)

        return result

    def check_max_value(self, name, label, observation_detail, value):
        ''' Check if an observation is greater than a desired value.
            Send a notification if time and cound thresholds have been met. '''
        result = None
        now = int(time.time())
        result2 = {
            'threshold_type': 'max',
            'threshold_value': observation_detail['value'],
            'name': name,
            'label': label,
            'current_value': value,
        }
        log.debug("  Max check if %s is greater than %s for %s%s", value, observation_detail['value'], name, label)
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        log.debug("    Time delta Max is %s and threshold is %s for %s%s", time_delta, observation_detail['wait_time'], name, label)
        log.debug("    Running count Max is %s and threshold is %s for %s%s",
                  observation_detail['counter'],
                  observation_detail['count'],
                  name,
                  label)

        if value > observation_detail['value']:
            if observation_detail['counter'] == 0:
                observation_detail['threshold_passed'] = {}
                observation_detail['threshold_passed']['timestamp'] = now
                observation_detail['threshold_passed']['notification_count'] = 0

            observation_detail['counter'] += 1
            if time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    observation_detail['threshold_passed']['notification_count'] += 1
                    result2['type'] = 'outside'
                    result2['notifications_sent'] = observation_detail['threshold_passed']['notification_count']
                    result2['date_time'] = observation_detail['threshold_passed']['timestamp']
                    result = result2
        else:
            if observation_detail['counter'] > 0:
                if observation_detail['threshold_passed']['notification_count'] > 0:
                    if observation_detail['return_notification']:
                        result2['type'] = 'within'
                        result2['notifications_sent'] = observation_detail['threshold_passed']['notification_count']
                        result2['date_time'] = observation_detail['threshold_passed']['timestamp']
                        result = result2
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

        if result:
            return namedtuple('Result', result.keys())(**result)

        return result

    def check_equal_value(self, name, label, observation_detail, value):
        ''' Check if an observation is not equal to desired value.
            Send a notification if time and cound thresholds have been met. '''
        result = None
        now = int(time.time())
        result2 = {
            'threshold_type': 'equal',
            'threshold_value': observation_detail['value'],
            'name': name,
            'label': label,
            'current_value': value,
        }
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

        if value != observation_detail['value']:
            if observation_detail['counter'] == 0:
                observation_detail['threshold_passed'] = {}
                observation_detail['threshold_passed']['timestamp'] = now
                observation_detail['threshold_passed']['notification_count'] = 0

            observation_detail['counter'] += 1
            if time_delta >= observation_detail['wait_time']:
                if observation_detail['counter'] >= observation_detail['count']:
                    observation_detail['threshold_passed']['notification_count'] += 1
                    result2['type'] = 'outside'
                    result2['notifications_sent'] = observation_detail['threshold_passed']['notification_count']
                    result2['date_time'] = observation_detail['threshold_passed']['timestamp']
                    result = result2
        else:
            if observation_detail['counter'] > 0:
                if observation_detail['threshold_passed']['notification_count'] > 0:
                    if observation_detail['return_notification']:
                        result2['type'] = 'within'
                        result2['notifications_sent'] = observation_detail['threshold_passed']['notification_count']
                        result2['date_time'] = observation_detail['threshold_passed']['timestamp']
                        result = result2
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

        if result:
            return namedtuple('Result', result.keys())(**result)

        return result

    def check_missing_value(self, observation, name, label, observation_detail):
        ''' Check if a notification should be sent for a missing value.'''
        log.debug("  Processing missing for %s%s", name, label)
        now = int(time.time())
        result2 = {
            'threshold_type': 'missing',
            'threshold_value': None,
            'name': name,
            'label': label,
            'current_value': None,
        }
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

        if observation_detail['counter'] == 0:
            self.missing_observations[observation] = {}
            self.missing_observations[observation]['missing_time'] = now
            self.missing_observations[observation]['notification_count'] = 0

        observation_detail['counter'] += 1

        if time_delta >= observation_detail['wait_time']:
            if observation_detail['counter'] >= observation_detail['count'] or observation_detail['last_sent_timestamp'] == 0:
                self.missing_observations[observation]['notification_count'] += 1
                result2['type'] = 'outside'
                result2['notifications_sent'] = self.missing_observations[observation]['notification_count']
                result2['date_time'] = self.missing_observations[observation]['missing_time']
                return namedtuple('Result', result2.keys())(**result2)
        return None

    def check_value_returned(self, observation, name, label, observation_detail, value):
        ''' Check if a notification should be sent when a missing value has returned. '''
        # ToDo: I think this needs work - think it is closer
        log.debug("  Processing returned value for observation %s%s", name, label)
        result = None
        now = int(time.time())
        result2 = {
            'threshold_type': 'missing',
            'threshold_value': None,
            'name': name,
            'label': label,
            'current_value': value,
        }
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

        if observation_detail['counter'] > 0:
            if self.missing_observations[observation]['notification_count'] > 0:
                if observation_detail['return_notification']:
                    result2['type'] = 'within'
                    result2['notifications_sent'] = self.missing_observations[observation]['notification_count']
                    result2['date_time'] = self.missing_observations[observation]['missing_time']
                    result = result2
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

        # Setting to 1 is a hack, this allows the time threshold to be met
        # But does not short circuit checking the count threshold
        # In otherwords, a value has been find since WeeWX started....
        if observation_detail['last_sent_timestamp'] == 0:
            observation_detail['last_sent_timestamp'] = 1

        if result:
            return namedtuple('Result', result.keys())(**result)

        return result

    async def _process_data(self, data, observations):
        # log.debug("Processing record: %s", data)
        now = time.time()
        tasks = []
        task_names = {}
        self.notifier.initialize()

        for _obs, observation_detail in observations.items():
            observation = observation_detail['weewx_name']

            if observation in data and data[observation] is not None:
                log.debug("Processing observation: %s%s", observation, observation_detail['label'])
                detail_type = 'missing'
                if observation_detail.get('missing', None):
                    result = self.check_value_returned(observation,
                                                       observation_detail['name'],
                                                       observation_detail['label'],
                                                       observation_detail[detail_type],
                                                       data[observation])
                    if result:
                        # This is when a missing value has returned
                        # Therefore, do not reset sent timestamp
                        # self.executor.submit(self._send_notification, event.packet)
                        task_name = f"{observation}-{detail_type}-{now}"
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

                detail_type = 'min'
                if observation_detail.get('min', None):
                    result = self.check_min_value(observation_detail['name'],
                                                  observation_detail['label'],
                                                  observation_detail[detail_type],
                                                  data[observation])
                    if result:
                        # self.executor.submit(self._send_notification, event.packet)
                        task_name = f"{observation}-{detail_type}-{now}"
                        task_names[task_name] = observation_detail[detail_type]
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

                detail_type = 'max'
                if observation_detail.get('max', None):
                    result = self.check_max_value(observation_detail['name'],
                                                  observation_detail['label'],
                                                  observation_detail[detail_type],
                                                  data[observation])
                    if result:
                        # self.executor.submit(self._send_notification, event.packet)
                        task_name = f"{observation}-{detail_type}-{now}"
                        task_names[task_name] = observation_detail[detail_type]
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

                detail_type = 'equal'
                if observation_detail.get('equal', None):
                    result = self.check_equal_value(observation_detail['name'],
                                                    observation_detail['label'],
                                                    observation_detail[detail_type],
                                                    data[observation])

                    if result:
                        # self.executor.submit(self._send_notification, event.packet)
                        task_name = f"{observation}-{detail_type}-{now}"
                        task_names[task_name] = observation_detail[detail_type]
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

            detail_type = 'missing'
            if observation not in data and observation_detail.get('missing', None):
                result = self.check_missing_value(observation,
                                                  observation_detail['name'],
                                                  observation_detail['label'],
                                                  observation_detail['missing'])
                if result:
                    # self.executor.submit(self._send_notification, event.packet)
                    task_name = f"{observation}-{detail_type}-{now}"
                    task_names[task_name] = observation_detail[detail_type]
                    tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

        if tasks:
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            for task in done:
                result = task.result()
                task_name = task.get_name()
                if task_name in task_names and result:
                    task_names[task_name]['last_sent_timestamp'] = now

        await self.notifier.finalize()

    def new_archive_record(self, event):
        """ Handle the new archive record event. """
        if not self.notifier.throttle_notification():
            asyncio.run(self._process_data(event.record, self.archive_observations))

    def new_loop_packet(self, event):
        """ Handle the new loop packet event. """
        if not self.notifier.throttle_notification():
            asyncio.run(self._process_data(event.packet, self.loop_observations))

    def shutDown(self):
        """Run when an engine shutdown is requested."""
        self.executor.shutdown(wait=False)

class AbstractNotifier():
    ''' Abstract class for sending notifications.'''
    def __init__(self):
        self.name = self.__class__.__name__

    async def initialize(self):
        ''' Perform any final processing for this 'round'. '''
        return

    def throttle_notification(self):
        ''' Check if the call should be performed or throttled.'''
        raise NotImplementedError()

    def build_title(self, msg_data):
        """ Build a title based on threshold status."""
        return f"Unexpected value for {msg_data.name}."

    def build_message(self, msg_data):
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

        if msg_data.threshold_type == 'missing' and msg_data.type == 'outside':
            return msg_missing_template.format(name=msg_data.name,
                                               label=msg_data.label,
                                               date_time=format_timestamp(msg_data.date_time),
                                               notifications_sent=msg_data.notifications_sent)

        if msg_data.threshold_type == 'missing' and msg_data.type == 'within':
            return msg_returned_template.format(name=msg_data.name,
                                                label=msg_data.label,
                                                date_time=format_timestamp(msg_data.date_time),
                                                current_value=msg_data.current_value,
                                                notifications_sent=msg_data.notifications_sent)

        return msg_template[msg_data.threshold_type][msg_data.type].format(date_time=format_timestamp(msg_data.date_time),
                                                                           name=msg_data.name,
                                                                           label=msg_data.label,
                                                                           threshold_value=msg_data.threshold_value,
                                                                           current_value=msg_data.current_value,
                                                                           notifications_sent=msg_data.notifications_sent
                                                                           )

    async def send_notification(self, _msg_data):
        ''' Send the notification.'''
        raise NotImplementedError('')

    async def finalize(self):
        ''' Perform any final processing for this 'round'. '''
        return

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
    config_dict['Notify']['enable'] = True

    notify = Notify(engine, config_dict)

    event = weewx.Event(weewx.NEW_LOOP_PACKET, packet=packet)

    notify.new_loop_packet(event)

    event = weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=packet)
    notify.new_archive_record(event)

    packet = {'dateTime': int(time.time()),
              'mon_extraTemp6': 6,
              'mon_extraTemp1': 1,
              }
    event = weewx.Event(weewx.NEW_ARCHIVE_RECORD, record=packet)
    notify.new_archive_record(event)

    notify.shutDown()

if __name__ == '__main__':
    main()
