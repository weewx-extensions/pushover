#
#    Copyright (c) 2025 Rich Bell <bellrichm@gmail.com>
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

    # The name of the notification provider.
    # There must be a matching section within '[Notify]'.
    # The default is PushOver.
    notifier = PushOver

    # Configuration data for the notification provider.
    [[PushOver]]
'''

import argparse
import asyncio
import logging
import os
import time
from collections import namedtuple

import configobj

import weewx
from weewx.engine import StdService
import weeutil
from weeutil.weeutil import to_bool, to_int

def format_timestamp(ts, format_str="%Y-%m-%d %H:%M:%S %Z"):
    ''' Format a timestamp for human consumption. '''
    return f"{time.strftime(format_str, time.localtime(ts))}"

class Logger:
    ''' Manage the logging '''
    def __init__(self):
        self.log = logging.getLogger(__name__)

    def logdbg(self, caller, msg):
        """ log debug messages """
        self.log.debug("(%s) %s", caller, msg)

    def loginf(self, caller, msg):
        """ log informational messages """
        self.log.info("(%s) %s", caller, msg)

    def logerr(self, caller, msg):
        """ log error messages """
        self.log.error("(%s) %s", caller, msg)

class Notify(StdService):
    """ Manage sending notifications."""
    def __init__(self, engine, config_dict):
        """Initialize an instance of Notify"""
        super().__init__(engine, config_dict)
        self.name = self.__class__.__name__

        self.logger = Logger()

        service_dict = config_dict.get('Notify', {})

        enable = to_bool(service_dict.get('enable', True))
        if not enable:
            self.logger.loginf(self.name, "Notify is not enabled, exiting")
            return

        notifier_name = service_dict.get('notifier', 'PushOver')
        notifier_dict = service_dict.get(notifier_name, None)
        if not notifier_dict:
            raise ValueError("'notifier' is required.")
        notifier_class_name = notifier_dict.get('extension', None)
        if not notifier_class_name:
            raise ValueError("'extension' is required.")
        notifier_class = weeutil.weeutil.get_object(notifier_class_name)
        self.notifier = notifier_class(self.logger, notifier_dict)

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
        self.logger.loginf(self.name, f"loop observations: {self.loop_observations}")

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
        self.logger.loginf(self.name, f"archive observations: {self.archive_observations}")

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
                    observation[value_type]['value'] = None
                observation[value_type]['count'] = int(config[value_type].get('count', count))
                observation[value_type]['wait_time'] = to_int(config[value_type].get('wait_time', wait_time))
                observation[value_type]['return_notification'] = to_bool(config[value_type].get('return_notification',
                                                                                                return_notification))
                observation[value_type]['last_sent_timestamp'] = 0
                observation[value_type]['counter'] = 0

        return observation

    def check_outside(self, notification_type, name, label, observation_detail, value):
        ''' Check if an observation is less than a desired value.
            Send a notification if time and cound thresholds have been met. '''
        result = None
        now = int(time.time())
        result2 = {
            'threshold_type': notification_type,
            'threshold_value': observation_detail['value'],
            'name': name,
            'label': label,
            'current_value': value,
        }
        self.logger.logdbg(self.name, f"  {notification_type} check {value} to {observation_detail['value']} for {name}{label}")
        time_delta = abs(now - observation_detail['last_sent_timestamp'])
        self.logger.logdbg(self.name, (f"    Time delta {notification_type} is {time_delta} and "
                                       f"threshold is {observation_detail['wait_time']} for {name}{label}"))
        self.logger.logdbg(self.name, (f"    Running count {notification_type} is {observation_detail['counter']} "
                                       f"and threshold is {observation_detail['count']} for {name}{label}"))

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

        if result:
            return namedtuple('Result', result.keys())(**result)

        return result

    def check_within(self, notification_type, name, label, observation_detail, value):
        ''' Check if an observation is not equal to desired value.
            Send a notification if time and cound thresholds have been met. '''
        result = None
        result2 = {
            'threshold_type': notification_type,
            'threshold_value': observation_detail['value'],
            'name': name,
            'label': label,
            'current_value': value,
        }
        self.logger.logdbg(self.name, f"  {notification_type} check {value} to {observation_detail['value']} for {name}{label}")
        self.logger.logdbg(self.name, (f"    Running count {notification_type} is {observation_detail['counter']} and "
                                       f"threshold is {observation_detail['count']} for {name}{label}"))

        if observation_detail['counter'] > 0:
            if observation_detail['threshold_passed']['notification_count'] > 0:
                if observation_detail['return_notification']:
                    result2['type'] = 'within'
                    result2['notifications_sent'] = observation_detail['threshold_passed']['notification_count']
                    result2['date_time'] = observation_detail['threshold_passed']['timestamp']
                    result = result2
                else:
                    self.logger.logdbg(self.name, (f"    Notification not requested for {name}{label} "
                                                   f"being outside {notification_type} at "
                                                   f"{format_timestamp(observation_detail['threshold_passed']['timestamp'])} "
                                                   f"and count of {observation_detail['counter']}."))
            else:
                self.logger.loginf(self.name, (f"No notifcations had been sent for {name}{label} outside {notification_type} at "
                                               f"{format_timestamp(observation_detail['threshold_passed']['timestamp'])} and "
                                               f"count of {observation_detail['counter']}."))

            observation_detail['counter'] = 0
            # Setting to 1 is a hack, this allows the time threshold to be met
            # But does not short circuit checking the count threshold
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
                self.logger.logdbg(self.name, f"Processing observation: {observation}{observation_detail['label']}")
                detail_type = 'missing'
                if observation_detail.get('missing', None):
                    result = self.check_within('missing',
                                               observation_detail['name'],
                                               observation_detail['label'],
                                               observation_detail[detail_type],
                                               data[observation])
                    if result:
                        # This is when a missing value has returned
                        # Therefore, do not reset sent timestamp
                        task_name = f"{observation}-{detail_type}-{now}"
                        self.logger.logdbg(self.name, f"Task, {task_name}, with {result}, has been submitted and not recorded.")
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

                detail_type = 'min'
                if observation_detail.get('min', None):
                    if data[observation] < observation_detail[detail_type]['value']:
                        result = self.check_outside('min',
                                                    observation_detail['name'],
                                                    observation_detail['label'],
                                                    observation_detail[detail_type],
                                                    data[observation])
                    else:
                        result = self.check_within('min',
                                                   observation_detail['name'],
                                                   observation_detail['label'],
                                                   observation_detail[detail_type],
                                                   data[observation])
                    if result:
                        task_name = f"{observation}-{detail_type}-{now}"
                        task_names[task_name] = observation_detail[detail_type]
                        self.logger.logdbg(self.name, f"Task, {task_name}, with {result}, has been submitted and recorded.")
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

                detail_type = 'max'
                if observation_detail.get('max', None):
                    if data[observation] > observation_detail[detail_type]['value']:
                        result = self.check_outside('max',
                                                    observation_detail['name'],
                                                    observation_detail['label'],
                                                    observation_detail[detail_type],
                                                    data[observation])
                    else:
                        result = self.check_within('max',
                                                   observation_detail['name'],
                                                   observation_detail['label'],
                                                   observation_detail[detail_type],
                                                   data[observation])
                    if result:
                        task_name = f"{observation}-{detail_type}-{now}"
                        task_names[task_name] = observation_detail[detail_type]
                        self.logger.logdbg(self.name, f"Task, {task_name}, with {result}, has been submitted and recorded.")
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

                detail_type = 'equal'
                if observation_detail.get('equal', None):
                    if data[observation] != observation_detail[detail_type]['value']:
                        result = self.check_outside('equal',
                                                    observation_detail['name'],
                                                    observation_detail['label'],
                                                    observation_detail[detail_type],
                                                    data[observation])
                    else:
                        result = self.check_within('equal',
                                                   observation_detail['name'],
                                                   observation_detail['label'],
                                                   observation_detail[detail_type],
                                                   data[observation])
                    if result:
                        task_name = f"{observation}-{detail_type}-{now}"
                        task_names[task_name] = observation_detail[detail_type]
                        self.logger.logdbg(self.name, f"Task, {task_name}, with {result}, has been submitted and recorded.")
                        tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

            detail_type = 'missing'
            if observation not in data and observation_detail.get('missing', None):
                result = self.check_outside('missing',
                                            observation_detail['name'],
                                            observation_detail['label'],
                                            observation_detail['missing'],
                                            None)
                if result:
                    task_name = f"{observation}-{detail_type}-{now}"
                    task_names[task_name] = observation_detail[detail_type]
                    self.logger.logdbg(self.name, f"Task, {task_name}, with {result}, has been submitted and recorded.")
                    tasks.append(asyncio.create_task(self.notifier.send_notification(result), name=task_name))

        if tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED, timeout=self.notifier.timeout)
            for task in done:
                result = task.result()
                task_name = task.get_name()
                self.logger.logdbg(self.name, f"Task, {task_name}, completed with result, {result}.")
                if task_name in task_names and result:
                    task_names[task_name]['last_sent_timestamp'] = now

            for task in pending:
                task_name = task.get_name()
                cancelled = task.cancel()
                self.logger.logerr(self.name, f"Task, {task_name}, cancellation attempt with result {cancelled}.")

        await self.notifier.finalize()

    def new_archive_record(self, event):
        """ Handle the new archive record event. """
        if not self.notifier.throttle_notification():
            asyncio.run(self._process_data(event.record, self.archive_observations))

    def new_loop_packet(self, event):
        """ Handle the new loop packet event. """
        if not self.notifier.throttle_notification():
            asyncio.run(self._process_data(event.packet, self.loop_observations))

class AbstractNotifier():
    ''' Abstract class for sending notifications.'''
    def __init__(self, logger, config_dict):
        self.name = self.__class__.__name__
        self.logger = logger
        self._timeout = config_dict.get('timeout', None)

    @property
    def timeout(self):
        ''' The time in seconds to wait for the notification processing to complete.'''
        return self._timeout

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

        msg_missing_template = {
            'outside': "{name}{label} missing at {date_time}, {notifications_sent} notifications sent.\n",
            'within': ("{name}{label} missing at {date_time} returned with value {current_value}, "
                       "{notifications_sent} notification sent.\n"),
        }

        if msg_data.threshold_type == 'missing' and msg_data.type == 'outside':
            return msg_missing_template[msg_data.type].format(name=msg_data.name,
                                                              label=msg_data.label,
                                                              date_time=format_timestamp(msg_data.date_time),
                                                              notifications_sent=msg_data.notifications_sent)

        if msg_data.threshold_type == 'missing' and msg_data.type == 'within':
            return msg_missing_template[msg_data.type].format(name=msg_data.name,
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
