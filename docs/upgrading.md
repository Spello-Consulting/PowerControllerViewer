# Upgrading the PowerControllerViewer app

Occasionally, or if you're having problems, you can upgrade to the latest version of the app:

```bash
cd /home/nick/scripts/PowerControllerViewer   # cd into the project root folder

git reset --hard origin/main                  # Reset to the remote main branch
```

Then restart the service:

```bash
sudo systemctl restart PowerControllerViewer
```

## For more information

See the [PowerControllerViewer issues list](https://github.com/Spello-Consulting/PowerControllerViewer/issues) for open / known / resolved bugs and enhancements.
