Fix: Make per-key module runnable and ship all subpackages

- Added src/gui/perkey/__main__.py so `python -m src.gui.perkey` works.
- Added missing __init__.py files under src/core, src/gui, and src/gui/widgets.
- Updated pyproject.toml to use setuptools package discovery so wheels include src.* and buildpython.*.
