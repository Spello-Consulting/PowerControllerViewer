# Plan: Move PowerControllerViewer off the public internet onto Tailscale

## Context

The app is currently the only service exposed to the internet (static IP
`188.114.97.7`, public DNS `power.elseyworld.com`, router port-forwards `80→8088`
for certbot and `443→4430` for the app, nginx terminating TLS and proxying to
the FastAPI/uvicorn app on `127.0.0.1:8000`).

The app logs show a large and constant volume of unwanted, hostile scanning
traffic — the cost of being publicly reachable. Every device we actually use to
reach the app (iPhone, iPad, Macs) is already on our Tailscale tailnet, and the
two producer apps that POST to the REST API (**PowerController**,
**LightingControl**) run either on this same box or on **pi-spello**, which is
also on the tailnet.

**Goal:** make the app reachable *only* over Tailscale, keep valid HTTPS (so
Chrome doesn't complain), and close all public inbound ports so the scanning
traffic simply can't reach us. No app code changes are required — the app keeps
binding `127.0.0.1:8000`.

**Chosen approach:** Tailscale **Serve** terminates HTTPS with an
auto-provisioned, auto-renewing Let's Encrypt certificate for the node's
MagicDNS name, and proxies to the local app. nginx and certbot are retired for
this app, and the public domain is fully decommissioned.

---

## Target architecture

```
Browser / Python client (on tailnet)
        │  HTTPS 443  (WireGuard-encrypted, tailnet only)
        ▼
  tailscaled on sydneyapp   ← terminates TLS with cert for
        │                      sydneyapp.desmana-eagle.ts.net
        │  HTTP → 127.0.0.1:8000
        ▼
  uvicorn / FastAPI (unchanged: production.yaml HostingIP 127.0.0.1, Port 8000)
```

- **No public inbound ports.** Tailscale reaches peers via NAT traversal
  (outbound UDP) and DERP relay fallback, so nothing needs to be forwarded from
  the router.
- Access is limited to tailnet devices (optionally further restricted by
  Tailscale ACLs).
- The cert is a publicly-trusted Let's Encrypt cert for the `*.ts.net` name, so
  both Chrome and the Python `requests`/`httpx` clients validate it with **no**
  warnings and **no** `verify=False`.

> **Important naming note:** the cert's name is the *full* MagicDNS FQDN
> `sydneyapp.desmana-eagle.ts.net`, not the bare `sydneyapp`. Reaching
> `https://sydneyapp` will trip a certificate-name-mismatch warning in Chrome.
> Use / bookmark the full `https://sydneyapp.desmana-eagle.ts.net` to get the
> clean, warning-free experience. (The tailnet was renamed from
> `taileaf681.ts.net` to `desmana-eagle.ts.net` — see step 0 below.)

---

## Implementation steps

All steps run **on sydneyapp** unless noted. None touch the app source.

### 0. Rename the tailnet (do this first)
Rename `taileaf681.ts.net` → `desmana-eagle.ts.net` in the admin console **before**
enabling certs/Serve, so the cert is minted for the final name with no reissue
churn.

Safe to do now: current access to sydneyapp is via `power.elseyworld.com`
and Tailscale IP/short-name, none of which carry the tailnet suffix, and no
`*.ts.net` HTTPS certs exist yet. The rename only changes the FQDN suffix
(`sydneyapp.taileaf681.ts.net` → `sydneyapp.desmana-eagle.ts.net`); Tailscale IPs
and the short MagicDNS name (`sydneyapp`) are unchanged. The old name is
released after rename, and Tailscale limits rename frequency — so this is the
name we keep.

### 1. Enable the prerequisites in the Tailscale admin console
- **MagicDNS**: enabled (DNS page).
- **HTTPS Certificates**: enabled (DNS page → "Enable HTTPS…"). This is what
  lets `tailscale serve` mint the Let's Encrypt cert.

### 2. Confirm the node name and cert
```bash
tailscale status          # confirm this node is "sydneyapp" and suffix is desmana-eagle.ts.net
```

Make sure `sydneyapp.desmana-eagle.ts.net` has propigated to the Let's encrypt servers:

```bash
dig +short NS desmana-eagle.ts.net
dig +short SOA desmana-eagle.ts.net
```

If these come back empty, the renamed zone isn't live on public DNS yet → pure propagation, just wait. If they return Tailscale nameservers, the zone exists and it's the challenge record specifically that's lagging (still resolves with time).

Now we can check that the certs work:

```bash
sudo tailscale cert sydneyapp.desmana-eagle.ts.net   # optional: pre-provision / prove certs work
```

### 3. Stand up Tailscale Serve (tailnet-only HTTPS → local app)
```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8000
sudo tailscale serve status     # verify: 443 → http://127.0.0.1:8000, tailnet only
```
- `--bg` persists the config across reboots (stored in tailscaled state).
- This is **Serve**, *not* **Funnel** — Serve is tailnet-only. Do **not** run
  `tailscale funnel`, which would re-expose the app to the public internet.
- WebSockets (`/ws`) are proxied transparently by Serve, so the live view keeps
  working.

**Verify from a second tailnet device** before tearing anything down:
```bash
curl -I https://sydneyapp.desmana-eagle.ts.net/         # 200, valid cert
# open https://sydneyapp.desmana-eagle.ts.net/ in Chrome → padlock, no warning, live WS updates
```

### 4. Reconfigure the producer apps (PowerController, LightingControl)
Change their target base URL from `https://power.elseyworld.com` to
`https://sydneyapp.desmana-eagle.ts.net`, keeping the existing `?key=…` access key
on `/api/submit`. Applies to both the local (same-box) and pi-spello instances.

- These live in **separate repos** (not in PowerControllerViewer), so the change
  is in each producer's own config, not here.
- Same-box producers *could* instead POST straight to
  `http://127.0.0.1:8000/api/submit?key=…` (loopback, no TLS needed). Optional
  simplification — pick one style and keep it consistent. Recommended: use the
  MagicDNS HTTPS URL everywhere so local and remote configs are identical.
- Verify each producer posts successfully (check `logs/logfile.log` on the app
  for accepted submits, and that a `403 invalid access key` is *not* logged).

### 5. Retire nginx for this app
Once step 3–4 are verified working:
```bash
sudo rm /etc/nginx/sites-enabled/PowerControllerViewer   # keep sites-available copy as reference
sudo nginx -t && sudo systemctl reload nginx
# if nginx serves nothing else on this box, optionally: sudo systemctl disable --now nginx
```

### 6. Retire certbot for the domain
```bash
sudo certbot delete --cert-name power.elseyworld.com     # remove the managed cert + renewal
sudo systemctl list-timers | grep certbot                # confirm no renewal remains
# (certbot's renew timer can stay; it just has nothing to renew once the cert is deleted)
```

### 7. Close the public front door (router / firewall)
- Remove the router NAT port-forwards: `80→8088` and `443→4430`.
- Close inbound `80` and `443` on the firewall.
- **Leave Tailscale working:** it needs only *outbound* UDP (typically 41641 /
  STUN 3478) plus DERP fallback — no inbound public port. Optionally forward
  UDP 41641 to sydneyapp for better direct-connection performance, but it is not
  required.
- The static IP and the `power.elseyworld.com` A record can be deleted (fully
  retire) or left dormant; with ports closed they expose nothing either way.

---

## Rollback

Serve config is separate from nginx, so rollback is low-risk:
- `sudo tailscale serve --https=443 off` removes the Serve mapping.
- Re-enable the nginx site (`sites-enabled` symlink) and reopen the port-forwards
  to restore the old public path. Keep `sites-available/PowerControllerViewer`
  and note the certbot cert name until the new setup has run for a few days.

## Verification checklist (end to end)
1. `sudo tailscale serve status` shows `443 → http://127.0.0.1:8000`.
2. From another tailnet device: `curl -I https://sydneyapp.desmana-eagle.ts.net/`
   returns `200` with a valid cert; Chrome shows a padlock and the live view
   updates over WebSocket.
3. Both producers (local + pi-spello) POST successfully to the new URL; app log
   shows accepted submits, no `403`.
4. From a device **off** the tailnet (e.g. phone on cellular with Tailscale
   disabled): `https://power.elseyworld.com` and the raw IP are now unreachable.
5. App still auto-starts after `sudo reboot` (systemd unit + `serve --bg`).

## Notes / non-goals
- No changes to `src/`, `configs/production.yaml`, the systemd unit, or the
  `launch.sh` / 1Password secrets flow — the app keeps listening on
  `127.0.0.1:8000` exactly as now.
- The existing `?key=` access key stays as defence-in-depth on `/api/submit` and
  `/ws`; the tailnet boundary is the primary control now.
- If finer access control is later wanted (e.g. only specific devices), add a
  Tailscale ACL rule for the sydneyapp node rather than app-level auth.
