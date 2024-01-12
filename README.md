# weewx-pushover

A WeeWX extension that sends alerts via [Pushover](https://pushover.net).

## Installation and configuring `weewx-pushover`

After installing `weewx-pushover`, edit the `Pushover` in `weewx.conf` as needed.

```text
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
    
    # Whether to chevk the 'loop' packet or 'archive' record' data.
    # The default is 'loop'
    # binding = loop

    # Pushover returns a status code in the range of 400 to 499 when the http request is bad.
    # In this case, WeeWX-Pushover will stop sending requests.
    # (On the assumption that all future requests will have the same error.)
    # An error will be logged ever 'client_error_log_frequency' seconds.
    # The default is 3600 seconds.
    # client_error_log_frequency = 3600

    # The number of times the threshold needs to be reached before sending a notification.
    # The default is 10.    
    # count = 10

    # Pushover returns a status code in the range of 500 to 599 when something went wrong on the server.
    # In this case WeeWX-Pushover will wait 'server_error_wait_period' before resuming sending requests.
    # (On the assumption that the server needs some time to be fixed.)
    # The default is 3600 seconds.
    # server_error_wait_period = 3600
    
    # The time to wait before sending another notification.
    # The default is 3600 seconds.
    # wait_time = 3600

    # The set of WeeWX observations to monitor.
    # Each subsection is the name of observation.
    # These can be anything
    # For example, inTemp_warn, inTemp_critical, etc
    [[observations]]
        [[[REPLACE_ME]]]

            # Override the 'binding' for this observation.
            # binding = loop

            The maximum value to monitor.
            # max =  REPLACE_ME

            # Override the max 'count' for this observation.
            # max_count = 10
            
            # Override the max 'wait_time' for this observation.
            # max_wait_time = 3600

            # The minimum value to monitor.
            # min = REPLACE_ME
            
            # The number of times the minimum needs to be reached before sending a notification.
            # The default is 10.
            # min_count = 10
            
            # Override the min 'count' for this observation.
            # min_count = 10
            
            # Override the min 'wait_time' for this observation.
            # min_wait_time = 3600
            
            # A descriptive name of this observation
            # Default is the observation name for this section.
            # name = 

            # The time in seconds to wait before sending another notification.
            # This is used to throttle the number of notifications.
            # The default is 3600 seconds.
            # wait_time = 3600

            # The WeeWX name of this observation
            # Default is the observation name for this section.
            # weewx_name = 
```
