# Production Deployment

This section shows you how to deploy the app on a Linux host (including a Raspberry Pi) so that it runs as a system service. It assumes:

1. The app has been deployed to _/home/nick/scripts/PowerControllerViewer_ and tested as per [Running the App](running.md).
2. The app is listening on port 8000 (change if required in the examples below).

## 1. Configure the app to accept local connections only

Edit the config.yaml file and set the _HostingIP_ key to 127.0.0.1. The web app will then only accept connections from the same host. Remote access, with HTTPS, is provided by [Tailscale Serve](tailscale.md).

## 2. Create a systemd service for the app

Copy the service file and edit it to review:

```bash
sudo cp deploy/sydneyapp/PowerControllerViewer.service /etc/systemd/system/PowerControllerViewer.service

sudo nano /etc/systemd/system/PowerControllerViewer.service
```

Key options to review:

- **ExecStart** and **WorkingDirectory**: change the paths to suit your installation.
- **User**: change the username to suit your installation.
- **Restart=on-failure**: restart if the script exits with a non-zero code.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable PowerControllerViewer
sudo systemctl start PowerControllerViewer
```

## 3. Check the status and logs

```bash
sudo systemctl status PowerControllerViewer
journalctl -u PowerControllerViewer.service -b
```

# Next Step >> [Remote Access with Tailscale](tailscale.md)
