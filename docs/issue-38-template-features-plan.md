# Issue #38 — Copy in features from the template web app

Port three template-webapp features into PowerControllerViewer's web UI:

1. **Day / Night / System display-mode toggle** in the title bar (persists in `localStorage`).
2. **System page** (`/system`) — platform info + psutil host metrics + **Number of data files loaded**.
3. **Config page** (`/config`) — dumps the active YAML config file.

Final title-bar right side order: **Clock → Display-mode toggle → System → Config**.

Reference: `/Users/nick/dev/LightingControl/docs/webapp-template-features-implementation-notes.md`
and the LightingControl implementation itself. This app's structure differs from the template
(templates/ + static/ at repo root, routes in `src/routes.py` via `register_routes`), so we adapt
rather than adopt the template's `src/` split — no file moves, `main.py` untouched.

## 1. Dependency
- `uv add psutil` (adds to `pyproject.toml` + `uv.lock`). Not currently installed.

## 2. `src/routes.py` — two new GET routes
Add inside `register_routes` (they can read the existing `config`, `state_store`, helpers):

- **`GET /system`** (async) — key-check via `_check_key`; build a `system_info` dict and render
  `system.html`. Fields, in order:
  - `Operating system` = `f"{platform.system()} {platform.release()}"`
  - `Platform` = `platform.platform()`
  - `Architecture` = `platform.machine()`
  - `Hostname` = `platform.node()`
  - `Python version` = `platform.python_version()`
  - `Uptime` = formatted `Xd Yh Zm` from `time.time() - psutil.boot_time()`
  - `Memory used` = `f"{virtual_memory().percent:.0f}%"`
  - `CPU load` = `f"{cpu_percent:.0f}%"` — **`await asyncio.to_thread(psutil.cpu_percent, 0.3)`** (blocks)
  - `Number of data files loaded` = `state_store.count()`  ← app-specific addition
  - **Excluded**: template's `Simulation mode` and `Cities loaded` rows.
  - Context also passes `access_key` (from `_key()`) and `refresh` so nav links keep `?key=` and the
    footer/base scripts work. Rendered via a small `page_data`-shaped context (see §4).
- **`GET /config`** (sync is fine) — key-check; read `config.config_path.read_text(encoding="utf-8")`
  inside `try/except OSError` (fallback message on error); render `config.html` with `config_text`
  and `config_path` (str). `config.config_path` is a `Path` exposed by `SCConfigManager`. Secrets live
  in `.env`, not the YAML, so dumping is safe.
- New imports: `asyncio` (already imported), `platform`, `time`, `psutil`.

## 3. `templates/_base.html` — title-bar controls + theme
The shared shell already has `<header>` with `.header-home` + `#clock`, an inline clock, and the WS
client. Changes:
- Add a **pre-paint theme script** in `<head>`: read `localStorage["theme"]` (default `"system"`),
  set `data-theme` on `<html>` before first paint (avoids a flash).
- Wrap the right side of the header in `<nav class="header-right">` containing, in order:
  `#clock`, a `#theme-toggle` `<button>`, a `/system` link, a `/config` link. Each nav link carries
  `?key={{ page_data.AccessKey }}` when an access key is set (reuse existing `page_data.AccessKey`).
- Add the **theme-toggle cycle** inline script: order `["system","light","dark"]`, icons `🖥️/☀️/🌙`,
  persisted to `localStorage`, updates `data-theme` + button title.
- Keep all existing timestamp/clock/WS logic intact.

## 4. New templates
- **`templates/system.html`** — `{% extends "_base.html" %}`; iterate `system_info.items()` into
  `.info-row`s inside `.info-card`, plus a back-to-home `.btn` (keeps `?key=`).
- **`templates/config.html`** — extends base; `config_path` in `.config-path`, contents in
  `<pre class="config-dump">`, back-to-home `.btn`.
- Both need a minimal `page_data` context (so base's header/footer render): `home_url`, `AccessKey`,
  and no `RefreshDelay` (or 0). The `/system` and `/config` routes build this small dict. The base's
  WS client is harmless on these pages (no matching device rows).

## 5. `static/styles.css` — theming (the bulk of the work)
The app currently hardcodes every colour. To make Light/Dark/System actually work:
- Define the palette as **CSS custom properties** in three blocks (mirroring LightingControl):
  - `:root { … }` — current light values, extracted into variables.
  - `:root[data-theme="dark"] { … }` — dark values.
  - `@media (prefers-color-scheme: dark) { :root[data-theme="system"], :root:not([data-theme]) { … } }`.
- Rewrite **every** hardcoded colour in the existing rules (header, cards, tables, buttons, badges,
  status indicators, temp displays, metering/schedule/switch tables, footer, nav) to reference the
  variables — a header-only theme looks broken in dark mode.
- Add new rules: `.header-right`, `.header-link`, `#theme-toggle`, and the info-page rules
  (`.info-page/.info-card/.info-row/.info-label/.info-value/.config-path/.config-dump`). `.btn` already
  exists — verify it themes correctly.

## 6. Verification
- `uv run ruff check src/ && uv run ruff format --check src/` clean.
- `uv run pytest` green (check for an existing test suite first; add a light TestClient check for
  `/system` + `/config` returning 200 if the repo already has web tests).
- Manual: run under uvicorn on a spare port; confirm header shows Clock → toggle → System → Config;
  toggle cycles System → Light → Dark and re-themes the whole page (home + summary + system + config);
  choice persists across reloads; `/system` shows the fields incl. data-files count and no
  Simulation/Cities rows; `/config` dumps the active YAML + path; live WS updates on home still work;
  if an access key is configured, nav links + WS preserve `?key=`.

## Notes / decisions
- No simulation mode in this app → omit the SIMULATION badge and Simulation/Cities rows.
- `psutil.cpu_percent` blocks → always via `asyncio.to_thread`.
- Access-key propagation: nav links + back-to-home button must include `?key=`.
- No `main.py` change, no directory restructure — smaller, lower-risk than the template's split.
