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
.venv/bin/python -m buildpython --run-steps=20   # Dead Code
.venv/bin/python -m buildpython --run-steps=21   # ShellCheck
```

Step 21 runs `shellcheck -x` on the managed installer/helper scripts. CI
installs ShellCheck. A local run **skips** the step when the binary is missing
(`command -v shellcheck`). On Fedora/Nobara:

```bash
sudo dnf install ShellCheck
```

# Full pipeline

Run the full pipeline with no trailing path argument.


```bash
.venv/bin/python -m buildpython
```