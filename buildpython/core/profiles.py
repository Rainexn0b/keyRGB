from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    include_steps: list[str]  # by step name


PROFILES: dict[str, Profile] = {
    "ci": Profile(
        name="ci",
        description="CI checks (compile + pytest)",
        include_steps=[
            "Compile",
            "Import Validation",
            "Import Scan",
            "Pip Check",
            "Pytest",
            "Repo Validation",
        ],
    ),
    "quick": Profile(
        name="quick",
        description="Quick checks (compile + pytest + lightweight analysis)",
        include_steps=[
            "Compile",
            "Import Validation",
            "Import Scan",
            "Pip Check",
            "Pytest",
            "Code Markers",
            "File Size",
            "Repo Validation",
        ],
    ),
    "full": Profile(
        name="full",
        description="Full local checks (includes optional lint if installed)",
        include_steps=[
            "Compile",
            "Import Validation",
            "Import Scan",
            "Pip Check",
            "Pytest",
            "Ruff",
            "Ruff Format",
            "Code Markers",
            "File Size",
            "LOC Check",
            "Type Check",
            "Repo Validation",
        ],
    ),
    "release": Profile(
        name="release",
        description="Release build (CI checks + AppImage)",
        include_steps=[
            "Compile",
            "Import Validation",
            "Import Scan",
            "Pip Check",
            "Pytest",
            "Repo Validation",
            "AppImage",
            "AppImage Smoke",
        ],
    ),
}
