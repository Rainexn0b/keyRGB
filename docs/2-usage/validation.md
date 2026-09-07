# Validation

Always use `.venv/bin/python`. A bare `python -m buildpython` on a distro
interpreter (especially 3.14) can fail Type Check when host numpy stubs use
syntax newer than the 3.10 mypy floor. KeyRGB does not import numpy.

```bash
.venv/bin/python -m pytest -q -o addopts=
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --run-steps="Type Check"
```

Hardware tests are opt-in and can talk to real devices:

```bash
KEYRGB_HW_TESTS=1 .venv/bin/python -m pytest -q -o addopts=
```

Full gate map: `docs/3-contributing/01-build_runner.md`.
