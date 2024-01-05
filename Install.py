#
#    Copyright (c) 2023 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
""" Installer for pushover extension. """

from io import StringIO

import configobj

from weecfg.extension import ExtensionInstaller

VERSION = '0.1.0'

EXTENSION_CONFIG = """
[Pushover]
    
    # Whether the service is enabled or not.
    # Valid values: True or False
    # Default is True.
    enable = False

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
    [[observations]]
        [[[REPLACE_ME]]]
            # A Descriptive name of this observation
            # Default is the WeeWX name.
            #name = 

            # The time in seconds to wait before sending another notification.
            # This is used to throttle the number of notifications.
            # The default is 3600 seconds.
            #wait_time = 3600

            # The number of times the minimum needs to be reached before sending a notification.
            # The default is 10.
            #min_count = 10

            # The minimum value to monitor.
            #min = REPLACE_ME

            # The number of times the minimum needs to be reached before sending a notification.
            # The default is 10.
            #max_count = 10

            The maximum value to monitor.
            #max =  REPLACE_ME
"""


def loader():
    """ Load and return the extension installer. """
    return PushoverInstaller()

class PushoverInstaller(ExtensionInstaller):
    """ The extension installer. """
    def __init__(self):
        install_dict = {
            'version': VERSION,
            'name': 'Pushover',
            'description': 'Send alerts via pushover.',
            'author': "Rich Bell",
            'author_email': "bellrichm@gmail.com",
            'files': [
                ('bin/user', ['bin/user/pushover.py']),
            ]
        }

        install_dict['config'] = configobj.ConfigObj(EXTENSION_CONFIG)
        install_dict['restful_services'] = 'user.pushover.Pushover'

        super().__init__(install_dict)
