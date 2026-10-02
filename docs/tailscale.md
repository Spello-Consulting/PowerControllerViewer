# Remote Access with Tailscale

Rather than exposing the web app to the internet (which attracts a constant stream of hostile scanning traffic), we recommend making it reachable **only over your [Tailscale](https://tailscale.com/) tailnet**. [Tailscale Serve](https://tailscale.com/kb/1242/tailscale-serve) terminates HTTPS using an automatically provisioned and renewed Let's Encrypt certificate and proxies to the local app. No nginx, certbot, domain name or router port-forwards are needed.

## Target architecture

```
Browser / sending app (on tailnet)
        │  HTTPS 443  (WireGuard-encrypted, tailnet only)
        ▼
  tailscaled on your host   ← terminates TLS with the cert for
        │                     myhost.<tailnet-name>.ts.net
        │  HTTP → 127.0.0.1:8000
        ▼
  uvicorn / FastAPI (HostingIP 127.0.0.1, Port 8000)
```

* No public inbound ports. Tailscale uses outbound NAT traversal with a relay fallback.
* Access is limited to devices on your tailnet (optionally restricted further with Tailscale ACLs).
* The certificate is publicly trusted, so browsers and Python clients validate it with no warnings and no `verify=False`.

!!! note
    The certificate is issued for the *full* MagicDNS name (for example `myhost.example-name.ts.net`), not the short host name. Use the full name in your browser and bookmarks to avoid a certificate-name-mismatch warning.

## Prerequisites

* The host running the app is on your tailnet and [Tailscale is installed](https://tailscale.com/kb/1347/installation).
* The app is running in a [production configuration](prod_deployment.md) with `HostingIP: 127.0.0.1` and `Port: 8000`.
* Every device that needs to view the app, and every host running a PowerController or LightingControl instance that posts to it, is on the same tailnet.

## 1. Enable MagicDNS and HTTPS certificates

In the Tailscale admin console, on the **DNS** page, make sure **MagicDNS** is enabled and click **Enable HTTPS...** under HTTPS Certificates.

## 2. Confirm the node name and certificate

On the host running the app:

```bash
tailscale status
```

Confirm the node name and the tailnet suffix (`<tailnet-name>.ts.net`). Optionally pre-provision the certificate to prove it works:

```bash
sudo tailscale cert myhost.example-name.ts.net
```

If you have just renamed your tailnet, the new DNS zone may take a little while to propagate to Let's Encrypt. You can check with `dig +short NS example-name.ts.net`; if the result is empty, wait and retry.

## 3. Start Tailscale Serve

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8000
sudo tailscale serve status
```

* `--bg` makes the configuration persist across reboots.
* This is **Serve**, not **Funnel**. Serve is tailnet-only. Do **not** run `tailscale funnel`, which would expose the app to the public internet.
* WebSockets (used for the live view) are proxied transparently.

Verify from a second device on your tailnet:

```bash
curl -I https://myhost.example-name.ts.net/
```

You should get a `200` with a valid certificate. Opening the same URL in a browser should show a padlock and live updates.

## 4. Point the sending apps at the new URL

In the config file of each PowerController or LightingControl instance, set the viewer website URL to the MagicDNS URL, keeping your access key if you use one:

```yaml
  WebsiteBaseURL: https://myhost.example-name.ts.net
  WebsiteAccessKey: <Optional access key>
```

Check the viewer's log file to confirm submits are accepted and that no `403 invalid access key` errors appear.

## Rolling back

```bash
sudo tailscale serve --https=443 off
```

This removes the Serve mapping without affecting the app itself.

## Notes

* The optional `AccessKey` remains useful as defence-in-depth; the tailnet boundary is the primary access control.
* For finer-grained control (for example, only specific devices), add a Tailscale ACL rule for the host rather than adding app-level authentication.
