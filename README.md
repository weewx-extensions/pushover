# notify

A WeeWX extension that sends alerts via [Pushover](https://pushover.net).

## Installation and configuring `notify`

After [installing](https://weewx.com/docs/5.0/utilities/weectl-extension/#install-an-extension) `notify`, edit the `Notify` section in `weewx.conf` as needed.

```text
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

            # The type of noitifcation. 
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
