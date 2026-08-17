# Optional package build

```bash
.venv/bin/python -m pip install -U build
.venv/bin/python -m build
```

Built wheels must include nested core resource JSON (reference defaults and
per-key tweak files under `src/core/resources/`). `pyproject.toml` ships them
via recursive `package-data` globs; CI and
`tests/core/resources/test_packaged_resources_unit.py` smoke-install the wheel
and load the ANSI starter defaults.
