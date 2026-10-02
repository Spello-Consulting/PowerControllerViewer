# Configuration file - HeartbeatMonitor section

Integration with a [Better Uptime](https://betterstack.com/uptime) heartbeat monitor to monitor uptime of the application.

| Key | Description |
|:--|:--|
| Enable | Set to True to enable integration with the heartbeat monitoring service. |
| WebsiteURL | Each time the app runs successfully, it hits this URL to record a heartbeat. If the app exits with a fatal error, it appends /fail to this URL. |
| HeartbeatTimeout | How long to wait for a response from the website before considering it down, in seconds. |
| Frequency | How often to post the state to the heartbeat monitor, in seconds. |
