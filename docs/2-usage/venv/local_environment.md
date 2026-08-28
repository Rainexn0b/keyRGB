# Local environment

Create the venv:

```bash
python3 -m venv .venv
```

Tray-capable Linux setups usually also need `gi` exposed to the venv. See `setup.md`.

Install dependencies (editable, with developer tools):

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

Runtime dependencies are declared in `[project].dependencies` in `pyproject.toml`;
the `dev` extra adds the developer tooling (pytest, ruff, mypy, etc.).
