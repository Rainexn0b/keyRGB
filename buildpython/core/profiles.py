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
            "Coverage",
            "Exception Transparency",
            "Dead Code",
            "Architecture Validation",
            "Repo Validation",
        ],
    ),
    "debt": Profile(
        name="debt",
        description="Debt-focused static analysis and architecture checks",
        include_steps=[
            "Compile",
            "Import Validation",
            "Pytest",
            "Code Markers",
            "File Size",
            "LOC Check",
            "Code Hygiene",
            "Coverage",
            "Exception Transparency",
            "Architecture Validation",
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
            "Coverage",
            "Exception Transparency",
            "Code Markers",
            "File Size",
            "Architecture Validation",
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
            "Coverage",
            "Exception Transparency",
            "Ruff",
            "Ruff Format",
            "Dead Code",
            "Code Markers",
            "File Size",
            "LOC Check",
            "Type Check",
            "Code Hygiene",
            "Architecture Validation",
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
            "Coverage",
            "Exception Transparency",
            "Architecture Validation",
            "Repo Validation",
            "AppImage",
            "AppImage Smoke",
        ],
    ),
}
