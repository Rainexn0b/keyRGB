# Package Structure Assessment: Normalizing the Python Packaging Layout

## Why this matters

Python package structure is not just a naming preference. It determines what import paths contributors learn, what setuptools installs, how console scripts resolve, how tests bootstrap imports, and how much hidden coupling exists between the repository checkout and the installed artifact.

KeyRGB's current layout is not broken. It is clearly intentional, and the repository already contains the code needed to make it work in both source-checkout and installed contexts. The maintainability issue is that the working setup is unconventional enough that the repository has to keep re-encoding the same assumption in packaging metadata, runtime launch helpers, test bootstrap code, and contributor workflows.

The core asymmetry is simple: the distribution is named `keyrgb`, but the importable top-level application package is `src`. That can be made to work, but it is the opposite of what most Python contributors expect when they see a directory named `src/`.

## Current state in this repo

Today, KeyRGB uses the repository root as the package discovery root and treats the literal `src/` directory as an importable Python package.

- The published project name is `keyrgb`, but runtime imports use `src.*`.
- Setuptools package discovery starts from `.` rather than from a non-importable source container directory.
- Package discovery currently includes both the app package tree (`src*`) and the build helper package tree (`buildpython*`).
- Console scripts in the project metadata point at `src.*` symbols.
- Local developer execution also leans on `python -m src...` and on a repo-root helper script.
- Test execution is configured to import directly from the checkout, and the tests add their own repo-root insertion helper on top of that.
- Some runtime code contains direct-execution fallbacks that add the repo root to `sys.path` if imports fail.

In other words, the current structure works because the repo explicitly teaches setuptools, the launcher scripts, the tests, and some runtime modules that `src` is the package name.

## Concrete evidence from the codebase

### Packaging metadata

[pyproject.toml](../../pyproject.toml) makes the current contract explicit:

- `[project].name = "keyrgb"`, so the distribution name is `keyrgb`.
- `[project.scripts]` maps user-facing commands to `src.*` targets such as `src.tray.entrypoint:main`, `src.gui.perkey:main`, and `src.core.diagnostics:main`.
- `[tool.setuptools.packages.find]` uses `where = ["."]` and `include = ["src*", "buildpython*"]`, so package discovery is rooted at the repository root and includes both the app tree and the build helper tree.
- `[tool.setuptools.package-data]` is keyed to the package name `src`.
- `[tool.pytest.ini_options]` sets `pythonpath = ["."]`, which makes the repository root importable during tests.
- `[tool.coverage.run]` uses `source = ["src"]`, so tooling is keyed to the current package name as well.

This is a coherent setup, but it means the package name `src` is part of the packaging contract, not just a folder choice.

### The `src` package is intentionally importable

[src/__init__.py](../../src/__init__.py) documents the intent directly: the project historically uses the directory name `src` as the import package, and keeping it importable allows commands such as `python -m src.<module>`.

[src/tray/__main__.py](../../src/tray/__main__.py) doubles down on that by explicitly documenting `python -m src.tray` as a supported local development path.

The repository-level launcher [keyrgb](../../keyrgb) also runs the tray with `python -B -m src.tray`, so the local developer flow is coupled to the package being named `src`.

### Entry points mix installed-console and module-launch workflows

The repo uses several overlapping entrypoint styles:

- Installed console scripts in [pyproject.toml](../../pyproject.toml).
- `python -m src...` launches from [keyrgb](../../keyrgb), [src/tray/ui/gui_launch.py](../../src/tray/ui/gui_launch.py), and [src/gui/calibrator/launch.py](../../src/gui/calibrator/launch.py).
- Direct-file execution fallbacks in GUI modules such as [src/gui/windows/uniform.py](../../src/gui/windows/uniform.py) and [src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py), which catch `ImportError` and then insert the repo root on `sys.path`.

This is useful operationally, but it also means the packaging shape has leaked into runtime behavior. The application is not only importable as `src`; multiple subsystems actively reconstruct that assumption when launched in alternate ways.

### Package-level entrypoint exports are not fully uniform

Some GUI packages re-export `main` from their package root, which aligns with console-script targets like `src.gui.perkey:main` and `src.gui.settings:main`:

- [src/gui/perkey/__init__.py](../../src/gui/perkey/__init__.py)
- [src/gui/settings/__init__.py](../../src/gui/settings/__init__.py)

The calibrator package is less uniform:

- [pyproject.toml](../../pyproject.toml) declares `keyrgb-calibrate = "src.gui.calibrator:main"`.
- [src/gui/calibrator/app.py](../../src/gui/calibrator/app.py) defines `main()`.
- [src/gui/calibrator/__main__.py](../../src/gui/calibrator/__main__.py) imports `main` from `.app`.
- [src/gui/calibrator/__init__.py](../../src/gui/calibrator/__init__.py) does not visibly re-export `main`.

That asymmetry may or may not be causing a user-visible problem today, but it is a good example of why the current entrypoint surface is harder to reason about than it needs to be.

### Launch helpers encode the current directory depth

[src/tray/ui/gui_launch.py](../../src/tray/ui/gui_launch.py) and [src/gui/calibrator/launch.py](../../src/gui/calibrator/launch.py) compute the repo or AppImage root with `Path(__file__).resolve().parents[3]`, with comments explaining that the target directory is the one that contains the `src/` package.

That works with the current path depth:

- source checkout: `<repo>/src/...`
- packaged app root: `.../usr/lib/keyrgb/src/...`

It is effective, but it is also structurally fragile. A future move from `src/<subpackages>` to `src/keyrgb/<subpackages>` would invalidate that fixed parent depth even if the runtime behavior stayed conceptually the same.

### Tests are explicitly shaped around import-from-checkout behavior

[tests/_paths.py](../../tests/_paths.py) computes the repository root and inserts it at the front of `sys.path`.

[tests/conftest.py](../../tests/conftest.py) imports that helper and calls it at import time.

Multiple tests repeat the same pattern directly before importing `src.*`; for example:

- [tests/gui/windows/test_support_window_unit.py](../../tests/gui/windows/test_support_window_unit.py)
- [tests/tray/ui/menu/test_tray_menu_capabilities_unit.py](../../tests/tray/ui/menu/test_tray_menu_capabilities_unit.py)
- [tests/core/diagnostics/core/test_diagnostics_unit.py](../../tests/core/diagnostics/core/test_diagnostics_unit.py)

This is on top of `[tool.pytest.ini_options].pythonpath = ["."]` in [pyproject.toml](../../pyproject.toml). That means the test environment currently has two layers of repo-root bootstrap:

1. pytest config makes `.` importable
2. test helpers and test modules also insert the repo root manually

That is not necessarily wrong, but it is a sign that the import contract is easy to forget and therefore repeatedly reinforced.

### The current shape is deeply baked into imports

A quick repository-wide scan on 2026-04-13 found:

- `300` files containing `from src...` or `import src...` across `src/` and `tests/`
- `22` files calling `ensure_repo_root_on_sys_path(...)`
- `7` subprocess launches invoking `python -m src...`

Those numbers do not mean the layout is bad. They do mean any structural normalization is a real migration, not a metadata-only cleanup.

### Contributor workflows already expose the ambiguity

[README.md](../../README.md) documents both installed commands such as `keyrgb`, `keyrgb-perkey`, and `keyrgb-calibrate`, and a repository-root developer command `./keyrgb`.

[CONTRIBUTING.md](../../CONTRIBUTING.md) tells contributors to run console commands such as `keyrgb`, `keyrgb-settings`, and `keyrgb-calibrate` locally.

That mixed story is understandable, but it creates onboarding questions:

- Should a contributor run the console scripts from an editable install?
- Should they use `./keyrgb` from the checkout?
- Should they run `python -m src.tray` or `python -m src.gui.perkey` directly?

The repository supports all of these in some form, which is flexible, but the flexibility comes from layout-specific conventions rather than from a single obvious packaging model.

## Risks / costs of the current structure

The current structure is workable, but it carries ongoing cost.

- It is cognitively surprising. In most Python projects, a directory named `src/` is a container for packages, not the package users import.
- The public distribution name and the internal import package name diverge. That increases mental overhead when reading docs, debugging import problems, or onboarding contributors.
- Tooling config is coupled to the current package name. Package-data, coverage source selection, pytest path bootstrapping, and console scripts all need coordinated updates if the layout changes.
- The runtime environment carries packaging-specific fallback code. Import fallback plus `sys.path` manipulation in GUI modules is a maintainability cost even when it works.
- Fixed path-depth assumptions make future cleanup harder. `parents[3]` is fine while the file tree stays exactly shaped the way it is now.
- Package discovery currently bundles `buildpython*` into the installable package set. If that is intentional, it should be treated as part of the product boundary. If it is accidental or only for local build flows, it expands the installed surface area unnecessarily.
- Tests that import directly from the checkout can hide issues that would only appear in a cleaner installed-package environment.
- Any future package rename has a large blast radius because the `src` import path is already referenced throughout application code, tests, subprocess launches, docs, and tooling.

None of these are immediate correctness failures. They are long-term maintenance taxes.

## Improvement options

### 1. Stabilize the current `src` package model

Keep `src` as the importable package name, but make the contract more explicit and more consistent.

This would include aligning package-level `main` exports, reducing duplicate bootstrap mechanisms, and replacing layout-fragile path calculations with shared helpers that discover the repo root structurally rather than by fixed parent depth.

This is the lowest-risk option. It does not solve the unconventional naming model, but it reduces accidental complexity around it.

### 2. Narrow the packaging boundary without renaming the app package

Still keep `src` as the runtime package name, but tighten what is considered part of the installable distribution.

The main question here is whether `buildpython*` should ship in the same wheel as the end-user application. If yes, that should be documented as a deliberate part of the distribution contract. If not, package discovery should become more explicit so internal build helper code is not silently part of the runtime install surface.

This option is still relatively low risk and would make the package boundary easier to reason about.

### 3. Migrate to a conventional named package under `src/`

Move application code into a real package such as `src/keyrgb/` and treat the outer `src/` directory as a non-importable source container in the conventional Python sense.

That would align the distribution name, import path, and contributor expectations much more cleanly. It would also remove the recurring need to explain that `src` is the package.

This is the most structurally correct option, but also the most expensive. Given how many files already import `src.*`, it should be treated as a planned migration rather than as opportunistic cleanup.

## Recommended direction

The best near-term direction is a two-stage approach.

First, normalize the current packaging contract without renaming the import package yet. That means treating the current `src` model as an intentional compatibility surface and cleaning up the sharp edges around it.

Recommended short-term cleanup:

- Make console-script targets and package exports consistent. Either point scripts at concrete modules or ensure package roots consistently re-export `main`.
- Replace fixed `parents[3]` path logic with shared repo-root detection helpers such as the structural search pattern already used in [src/core/runtime/imports.py](../../src/core/runtime/imports.py).
- Decide whether `buildpython` is truly part of the shipped distribution. Reflect that decision explicitly in setuptools discovery.
- Pick one primary test import bootstrap strategy and document it, rather than relying on both `pythonpath = ["."]` and repeated manual repo-root insertion as the default pattern.
- Clarify in contributor docs when to use installed console scripts versus checkout-local wrappers such as [keyrgb](../../keyrgb).

Then, if maintainers still want to normalize the package layout after that cleanup, perform a dedicated migration to a conventional named package. At that point the repo will already have less ambiguity and fewer layout-specific shortcuts, which lowers migration risk.

## Migration cautions

If the repo eventually moves away from the importable `src` package, the migration needs to account for more than just import statements.

- Update all console-script targets in [pyproject.toml](../../pyproject.toml).
- Update package-data keys and coverage source selection in [pyproject.toml](../../pyproject.toml).
- Update subprocess launch targets in [src/tray/ui/gui_launch.py](../../src/tray/ui/gui_launch.py) and [src/gui/calibrator/launch.py](../../src/gui/calibrator/launch.py).
- Remove or rewrite direct-execution `ImportError` fallbacks in GUI modules such as [src/gui/windows/uniform.py](../../src/gui/windows/uniform.py) and [src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py).
- Rework repo-root detection so it no longer depends on the current nesting depth.
- Update tests that import `src.*` directly and tests that assume the repo root should be inserted into `sys.path`.
- Revisit docs and contributor instructions that mention current launcher patterns.
- Consider temporary compatibility shims only if downstream scripts or packaging flows truly need them; otherwise, a single explicit migration is usually easier to reason about than a long-lived alias layer.

One specific caution: any move to `src/keyrgb/...` changes path depth under source checkout. Code that currently uses `Path(__file__).resolve().parents[3]` will no longer resolve the same root.

## Suggested sequencing

1. Document the current contract clearly, including whether `buildpython` is intentionally part of the installed distribution.
2. Normalize entrypoint declarations so package-level and module-level `main` ownership is consistent.
3. Replace fixed parent-depth repo-root calculations with a shared structural helper.
4. Choose and document one primary test bootstrap strategy for import-from-checkout behavior.
5. Tighten setuptools discovery so the installable package set matches the intended product boundary.
6. Only after the above cleanup, evaluate whether a full migration to `src/keyrgb/` still delivers enough value to justify the broad import rewrite.
7. If the migration proceeds, do it as an explicit repo-wide change that updates imports, subprocess launches, tooling config, and developer docs together.

The important point is sequencing: low-risk cleanup can reduce ambiguity now, while a conventional package-layout migration should be treated as a separate structural change with its own branch, review scope, and regression checks.
