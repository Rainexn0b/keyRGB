Refactor: Reorganize project structure and modularize Per-Key Editor

- Moved source files to src/core, src/gui, and src/legacy for better organization.
- Refactored monolithic src/gui_perkey.py into src/gui/perkey package.
- Updated build system to validate new module paths.
- Updated entry points in pyproject.toml and launcher scripts.
- Fixed CI import validation by using lazy imports for pystray in src/gui/tray.py.
