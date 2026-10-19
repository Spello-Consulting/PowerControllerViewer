# PowerControllerViewer Web Interface

A simple Python web app used to display current status and recent history from one or more PowerController and/or LightingControl installations.

## Documentation

Full installation, configuration and deployment documentation is at **https://spello-consulting.github.io/PowerControllerViewer/**.

The documentation source is in the `docs/` folder and is built with [MkDocs](https://www.mkdocs.org/) (Material theme). To preview or publish it:

```bash
uv sync --extra dev
uv run mkdocs serve                # preview at http://127.0.0.1:8000
uv run mkdocs gh-deploy --force    # publish to GitHub Pages
```

## Development checks

Install the development tools and run the regression suite:

```bash
uv sync --extra dev
uv run pytest
uv run pytest --cov --cov-report=term-missing
uv run ruff check tests
uv run ruff format --check tests
uv run mypy --strict tests
```

Coverage includes every Python module under `src/`, including branches, and fails
below 95%. Add `--cov-report=html` for a browsable report in `htmlcov/index.html`.

Tests are split by application component: ingestion, state storage, routes,
system/log pages, WebSockets, housekeeping, startup/configuration, and individual
view models under `tests/view_models/`. Shared fixtures and payload factories live
in `tests/conftest.py` and `tests/helpers.py`.

The suite uses temporary state/log directories, a fixed application clock and
mocked host metrics. HTTP and WebSocket tests use the real routes, templates and
state store through FastAPI's in-process test client. Startup tests replace
configuration and logging before loading the entry point; no `.env` file,
1Password session, live devices or running web server is required.

The mypy configuration checks test code strictly while skipping imports of the
existing application modules and allowing the untyped `sc-foundation-services`
and Cerberus dependencies. Full strict typing of `src/` remains separate work;
this test expansion does not change application behaviour.
