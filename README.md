# weewx-pushover
Send alerts via Pushover when WeeWX observations are out of a specified range
See, https://pushover.net

Configuration:
```
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
```
