# Local environment

Create the venv:

```bash
python3 -m venv .venv
```

Tray-capable Linux setups usually also need `gi` exposed to the venv. See `docs/venv/setup.md`.

Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e '.[qt,dev]'
```
