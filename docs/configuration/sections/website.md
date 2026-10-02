# Configuration file - Website section

Settings for the built-in web server.

| Key | Description |
|:--|:--|
| HostingIP | The IP address that the web server listens on. Set to 0.0.0.0 to listen on all network interfaces on the host. In a production environment behind [Tailscale Serve](../../tailscale.md), set to 127.0.0.1. |
| Port | The port to listen on. Defaults to 8000. |
| PageAutoRefresh | Delay in seconds before any web page does a full automatic browser refresh (to update non-data elements). Defaults to 10 seconds. Set to blank or 0 to disable refresh. |
| DebugMode | Enable or disable debug mode for the web server (should be False in production). |
| AccessKey | An optional alphanumeric key used to protect access to the web site. If specified, the key must be included in the website URL, for example: `http://127.0.0.1:8000/home?key=abcdef123456`. Alternatively, set the `VIEWER_ACCESS_KEY` environment variable in the .env file.<br><br>If you specify a key, the same key must also be set for the _WebsiteAccessKey_ parameter in the sending application's configuration file. |
