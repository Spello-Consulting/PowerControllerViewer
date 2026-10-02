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
