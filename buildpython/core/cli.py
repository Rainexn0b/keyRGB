from __future__ import annotations

import argparse
from collections.abc import Iterable

from ..steps.step_defs import steps as all_steps
from .profiles import PROFILES
from .runner import run
from .runtime_log import RUNTIME_LAUNCHERS, RUNTIME_LOG_MODES, capture_runtime_log


def _parse_csv(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return []
    if "," in raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return [p for p in raw.split() if p]


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
        for name in prof.include_steps:
            s = by_name.get(name.lower())
            if s is None:
                raise SystemExit(f"Profile '{profile}' references unknown step: {name!r}")
            selected.append(s)
    else:
        # Default run: use the full profile while keeping black opt-in.
        prof = PROFILES["full"]
        for name in prof.include_steps:
            s = by_name.get(name.lower())
            if s is None:
                raise SystemExit(f"Profile 'full' references unknown step: {name!r}")
            selected.append(s)

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


def _maybe_add_appimage(selected: list, *, enabled: bool):
    if not enabled:
        return selected

    steps = all_steps()
    appimage = next((s for s in steps if s.name.lower() == "appimage"), None)
    smoke = next((s for s in steps if s.name.lower() == "appimage smoke"), None)

    if appimage is None:
        raise SystemExit("AppImage step not found (step registry out of date)")
    if smoke is None:
        raise SystemExit("AppImage Smoke step not found (step registry out of date)")

    out = list(selected)
    if not any(s.name.lower() == "appimage" for s in out):
        out.append(appimage)
    if not any(s.name.lower() == "appimage smoke" for s in out):
        out.append(smoke)
    return out


def _maybe_add_black(selected: list, *, enabled: bool):
    if not enabled:
        return selected

    steps = all_steps()
    black = next((s for s in steps if s.name.lower() == "black"), None)
    if black is None:
        raise SystemExit("Black step not found (step registry out of date)")

    if any(s.name.lower() == "black" for s in selected):
        return selected

    return [*selected, black]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--profile", choices=sorted(PROFILES.keys()), help="Run a predefined profile")
    parser.add_argument("--list-profiles", action="store_true", help="List profiles and exit")
    parser.add_argument("--list-steps", action="store_true", help="List steps and exit")
    parser.add_argument("--run-steps", help="Comma/space-separated list of step numbers or names")
    parser.add_argument("--skip-steps", help="Comma/space-separated list of step numbers or names")
    parser.add_argument("--verbose", action="store_true", help="Print stdout/stderr for steps")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Run all steps even if one fails",
    )
    parser.add_argument(
        "--with-appimage",
        action="store_true",
        help="Also build the AppImage after the selected steps",
    )
    parser.add_argument(
        "--with-black",
        action="store_true",
        help="Also run black formatting check after the selected steps",
    )
    parser.add_argument(
        "--capture-runtime-log",
        nargs="?",
        const="full",
        choices=RUNTIME_LOG_MODES,
        metavar="MODE",
        help="Capture KeyRGB runtime logs (debug, brightness, or full; default: full)",
    )
    parser.add_argument(
        "--runtime-log-launcher",
        choices=RUNTIME_LAUNCHERS,
        default="installed",
        help="Runtime used by --capture-runtime-log (default: installed)",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.capture_runtime_log is not None:
        capture_conflicts = (
            args.profile is not None
            or args.list_profiles
            or args.list_steps
            or args.run_steps is not None
            or args.skip_steps is not None
            or args.verbose
            or args.continue_on_error
            or args.with_appimage
            or args.with_black
        )
        if capture_conflicts:
            parser.error("--capture-runtime-log cannot be combined with build step or profile options")
        return capture_runtime_log(
            mode=str(args.capture_runtime_log),
            launcher=str(args.runtime_log_launcher),
        )

    if args.runtime_log_launcher != "installed":
        parser.error("--runtime-log-launcher requires --capture-runtime-log")

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

    selected = _maybe_add_black(selected, enabled=args.with_black)
    selected = _maybe_add_appimage(selected, enabled=args.with_appimage)

    if not selected:
        print("No steps selected.")
        return 2

    return run(selected, verbose=args.verbose, continue_on_error=args.continue_on_error)
