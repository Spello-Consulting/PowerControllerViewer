# Configuration

The PowerControllerViewer application is configured using the **config.yaml** file in the project root folder. An [example Configuration File](example_config.md) is provided as part of the installation - copy it to config.yaml to get started.

The config file supports the following sections. A separate help page is provided for each one.

<div class="config-table" markdown>

| Section | Description | Required |
|:--|:--|:--|
| [Website](sections/website.md) | Settings for the built-in web server | Yes |
| [Files](sections/files.md) | Location of the log file and state data retention | Yes |
| [HeartbeatMonitor](sections/heartbeat_monitor.md) | Integration with a Better Uptime heartbeat monitor | No |

</div>

When the app starts, it validates the contents of the config file and reports any errors to the console.

## Environment variables

Secrets can be supplied via a `.env` file in the project root folder instead of the config file. For example, `VIEWER_ACCESS_KEY` overrides the `Website: AccessKey` setting.
