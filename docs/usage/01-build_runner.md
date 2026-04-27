# Build runner / gates

```bash
.venv/bin/python -m buildpython --list-profiles
.venv/bin/python -m buildpython --list-steps
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --profile=full --with-black
.venv/bin/python -m buildpython --profile=full --with-black --continue-on-error
.venv/bin/python -m buildpython --profile=ci --with-appimage
.venv/bin/python -m buildpython --profile=release
```

# Step-specific runs

Check the current step map before using numeric selectors. Step numbers can move as
the pipeline changes.

```bash
.venv/bin/python -m buildpython --run-steps=1,2
.venv/bin/python -m buildpython --run-steps="Ruff,Ruff Format,Black"
.venv/bin/python -m buildpython --run-steps="Import Validation,Import Scan,Pip Check"
.venv/bin/python -m buildpython --run-steps=14,15
```

# Targeted gates

```bash
.venv/bin/python -m buildpython --list-steps
.venv/bin/python -m buildpython --run-steps=13   # Type Check in the current step map
.venv/bin/python -m buildpython --run-steps=16   # Code Hygiene in the current step map
.venv/bin/python -m buildpython --run-steps=19   # Exception Transparency
```

# Full pipeline

Run the full pipeline with no trailing path argument.


```bash
.venv/bin/python -m buildpython
```