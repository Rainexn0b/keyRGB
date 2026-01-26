from __future__ import annotations

import os
import shutil
from pathlib import Path


def bundle_libappindicator(*, appdir: Path) -> None:
    """Bundle libappindicator native library + dependencies into the AppImage.

    libappindicator provides native tray icon support on Ubuntu/GNOME systems.
    We bundle it so the AppImage works without requiring system packages.
    """

    usr_lib = appdir / "usr" / "lib"
    usr_lib.mkdir(parents=True, exist_ok=True)

    # Common system library paths.
    lib_search_paths = [
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/lib64"),
        Path("/usr/lib"),
    ]

    # Bundle the full indicator stack:
    # - libappindicator3 / ayatana-appindicator3 (high-level API)
    # - libayatana-indicator3 / libindicator3 (underlying indicator library)
    # - libayatana-ido3 (indicator display objects - GTK widgets for indicators)
    # - libdbusmenu-gtk3 (menu protocol)
    lib_patterns = [
        "libappindicator3.so*",
        "libayatana-appindicator3.so*",
        "libayatana-indicator3.so*",
        "libindicator3.so*",
        "libayatana-ido3-0.4.so*",
        "libdbusmenu-gtk3.so*",
    ]

    def find_and_bundle_lib(patterns: list[str]) -> bool:
        """Find a library by pattern and bundle it with all symlink variants."""
        for search_path in lib_search_paths:
            if not search_path.exists():
                continue
            for pattern in patterns:
                matches = list(search_path.glob(pattern))
                if not matches:
                    continue

                bundled_files: set[str] = set()
                for candidate in matches:
                    current = candidate
                    while current.exists():
                        dst = usr_lib / current.name
                        if current.name not in bundled_files:
                            if current.is_symlink():
                                link_target = os.readlink(current)
                                if os.path.isabs(link_target):
                                    link_target = os.path.basename(link_target)
                                if dst.exists() or dst.is_symlink():
                                    dst.unlink()
                                os.symlink(link_target, dst)
                            else:
                                shutil.copy2(current, dst)
                            bundled_files.add(current.name)

                        if current.is_symlink():
                            next_target = current.readlink()
                            if next_target.is_absolute():
                                current = next_target
                            else:
                                current = current.parent / next_target
                        else:
                            break

                if bundled_files:
                    return True
        return False

    bundled_any = False
    for pattern in lib_patterns:
        if find_and_bundle_lib([pattern]):
            bundled_any = True

    if not bundled_any:
        # No indicator libraries found; AppImage will fall back to basic tray icon.
        return
