from __future__ import annotations

import argparse
from typing import Iterable

from .profiles import PROFILES
from .runner import run
from ..steps.step_defs import steps as all_steps


def _parse_csv(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return []
    return [p.strip() for p in raw.replace(" ", ",").split(",") if p.strip()]


def _list_profiles() -> None:
    print("Available profiles:")
    for name, profile in sorted(PROFILES.items()):
        print(f"  {name:<8} - {profile.description}")


def _list_steps() -> None:
    for s in all_steps():
        print(f"  {s.number:>2}  {s.name:<12} - {s.description}")


def _select_steps(run_steps: list[str] | None, skip_steps: list[str] | None, profile: str | None):
    steps = all_steps()
    by_number = {str(s.number): s for s in steps}
    by_name = {s.name.lower(): s for s in steps}

    selected = []

    if run_steps is not None:
        for token in run_steps:
            if token in by_number:
                selected.append(by_number[token])
                continue
            s = by_name.get(token.lower())
            if s is not None:
                selected.append(s)
                continue
            raise SystemExit(f"Unknown step selector: {token!r}")
    elif profile is not None:
        prof = PROFILES[profile]
        include = {n.lower() for n in prof.include_steps}
        selected = [s for s in steps if s.name.lower() in include]
    else:
        selected = steps

    if skip_steps:
        skip = {t.lower() for t in skip_steps}
        selected = [s for s in selected if str(s.number) not in skip and s.name.lower() not in skip]

    # Deduplicate
    seen = set()
    uniq = []
    for s in selected:
        if s.number in seen:
            continue
        seen.add(s.number)
        uniq.append(s)

    return uniq


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--profile", choices=sorted(PROFILES.keys()), help="Run a predefined profile")
    parser.add_argument("--list-profiles", action="store_true", help="List profiles and exit")
    parser.add_argument("--list-steps", action="store_true", help="List steps and exit")
    parser.add_argument("--run-steps", help="Comma/space-separated list of step numbers or names")
    parser.add_argument("--skip-steps", help="Comma/space-separated list of step numbers or names")
    parser.add_argument("--verbose", action="store_true", help="Print stdout/stderr for steps")
    parser.add_argument("--continue-on-error", action="store_true", help="Run all steps even if one fails")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_profiles:
        _list_profiles()
        return 0

    if args.list_steps:
        _list_steps()
        return 0

    selected = _select_steps(
        run_steps=_parse_csv(args.run_steps),
        skip_steps=_parse_csv(args.skip_steps),
        profile=args.profile,
    )

    if not selected:
        print("No steps selected.")
        return 2

    return run(selected, verbose=args.verbose, continue_on_error=args.continue_on_error)
