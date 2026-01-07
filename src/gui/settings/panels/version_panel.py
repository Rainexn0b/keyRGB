from __future__ import annotations

import json
import re
import webbrowser
from importlib import metadata
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

import tkinter as tk
from tkinter import ttk

from src.core.runtime.imports import repo_root_from
from src.core.utils.version_check import compare_versions, normalize_version_text
from src.gui.utils.tk_async import run_in_thread


class VersionPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        root: tk.Misc,
        get_status_label: Callable[[], ttk.Label],
    ) -> None:
        self._root = root
        self._get_status_label = get_status_label

        title = ttk.Label(parent, text="Version", font=("Sans", 11, "bold"))
        title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            parent,
            text=(
                "Shows the KeyRGB version you're running and checks GitHub to see\n"
                "whether you're on the latest stable release (and also shows the latest pre-release)."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 8))

        grid = ttk.Frame(parent)
        grid.pack(fill="x", pady=(0, 8))

        ttk.Label(grid, text="Installed", font=("Sans", 9)).grid(row=0, column=0, sticky="w")
        self.lbl_installed_version = ttk.Label(grid, text="?", font=("Sans", 9))
        self.lbl_installed_version.grid(row=0, column=1, sticky="w", padx=(10, 0))

        ttk.Label(grid, text="Latest (stable)", font=("Sans", 9)).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.lbl_latest_stable_version = ttk.Label(grid, text="Checking…", font=("Sans", 9))
        self.lbl_latest_stable_version.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(4, 0))

        ttk.Label(grid, text="Latest (pre-release)", font=("Sans", 9)).grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.lbl_latest_prerelease_version = ttk.Label(grid, text="Checking…", font=("Sans", 9))
        self.lbl_latest_prerelease_version.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(4, 0))

        self.lbl_update_status = ttk.Label(parent, text="", font=("Sans", 9))
        self.lbl_update_status.pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=(0, 2))

        self.btn_open_repo = ttk.Button(btn_row, text="Open repo", command=self._open_repo)
        self.btn_open_repo.pack(side="left")

        self._installed_version = self._installed_version_text()
        self.lbl_installed_version.configure(text=self._installed_version)
        self.lbl_latest_stable_version.configure(text="Checking…")
        self.lbl_latest_prerelease_version.configure(text="Checking…")
        self.lbl_update_status.configure(text="")

        self.start_latest_version_check()

    def start_latest_version_check(self) -> None:
        def work() -> tuple[str | None, str | None]:
            return self._fetch_latest_github_versions()

        def on_done(result: tuple[str | None, str | None]) -> None:
            stable, prerelease = result
            self._apply_latest_version_result(stable, prerelease)

        run_in_thread(self._root, work, on_done)

    def _installed_version_text(self) -> str:
        repo_version = self._repo_version_text()
        if repo_version:
            v_norm = normalize_version_text(repo_version) or str(repo_version).strip()
            display = (
                f"v{v_norm}" if not str(repo_version).strip().lower().startswith("v") else str(repo_version).strip()
            )
            return f"{display} (dev)"

        try:
            v = metadata.version("keyrgb")
        except Exception:
            return "unknown"

        v_norm = normalize_version_text(v) or str(v).strip()
        return f"v{v_norm}" if not str(v).strip().lower().startswith("v") else str(v).strip()

    @staticmethod
    def _repo_version_text() -> str | None:
        """Best-effort: if we're running from a source checkout, read version from pyproject.toml."""

        try:
            root = repo_root_from(__file__)
        except Exception:
            return None

        pyproject = Path(root) / "pyproject.toml"
        if not pyproject.exists():
            return None

        try:
            # Avoid depending on TOML parsing libraries here. This panel is UI-only
            # and should work even on older Python runtimes used by some build systems.
            text = pyproject.read_text(encoding="utf-8", errors="replace")

            in_project = False
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue

                # Section header
                if line.startswith("[") and line.endswith("]"):
                    in_project = line == "[project]"
                    continue

                if not in_project:
                    continue

                # Strip trailing comments (good enough for version=...)
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue

                m = re.match(r"^version\s*=\s*(['\"])(?P<v>[^'\"]+)\1\s*$", line)
                if m:
                    return m.group("v").strip() or None

            return None
        except Exception:
            return None

    def _fetch_latest_github_versions(self) -> tuple[str | None, str | None]:
        """Return (latest_stable_tag, latest_prerelease_tag)."""

        url = "https://api.github.com/repos/Rainexn0b/keyRGB/releases?per_page=30"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "keyrgb",
        }

        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=5.0) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
        except Exception:
            return None, None

        if not isinstance(data, list):
            return None, None

        stable: str | None = None
        prerelease: str | None = None

        for rel in data:
            if not isinstance(rel, dict):
                continue
            if rel.get("draft"):
                continue
            tag = rel.get("tag_name")
            if not isinstance(tag, str) or not tag.strip():
                continue

            if rel.get("prerelease") and prerelease is None:
                prerelease = tag.strip()
            if not rel.get("prerelease") and stable is None:
                stable = tag.strip()

            if stable is not None and prerelease is not None:
                break

        return stable, prerelease

    def _apply_latest_version_result(self, stable_tag: str | None, prerelease_tag: str | None) -> None:
        if not stable_tag and not prerelease_tag:
            self.lbl_latest_stable_version.configure(text="Unknown")
            self.lbl_latest_prerelease_version.configure(text="Unknown")
            self.lbl_update_status.configure(text="Couldn't check GitHub")
            return

        if stable_tag:
            stable_norm = normalize_version_text(stable_tag) or stable_tag
            stable_display = f"v{stable_norm}" if not str(stable_tag).lower().startswith("v") else str(stable_tag)
            self.lbl_latest_stable_version.configure(text=stable_display)
        else:
            stable_display = None
            self.lbl_latest_stable_version.configure(text="Unknown")

        if prerelease_tag:
            pre_norm = normalize_version_text(prerelease_tag) or prerelease_tag
            pre_display = f"v{pre_norm}" if not str(prerelease_tag).lower().startswith("v") else str(prerelease_tag)
            self.lbl_latest_prerelease_version.configure(text=pre_display)
        else:
            self.lbl_latest_prerelease_version.configure(text="None")

        if stable_display is None:
            self.lbl_update_status.configure(text="Couldn't compare versions")
            return

        cmp = compare_versions(self._installed_version, stable_display)
        if cmp is None:
            self.lbl_update_status.configure(text="Couldn't compare versions")
        elif cmp == 0:
            self.lbl_update_status.configure(text="✓ You are on the latest stable version")
        elif cmp < 0:
            self.lbl_update_status.configure(text=f"Update available (stable): {stable_display}")
        else:
            self.lbl_update_status.configure(text="You are ahead of the latest stable release")

    def _open_repo(self) -> None:
        url = "https://github.com/Rainexn0b/keyRGB"
        try:
            ok = bool(webbrowser.open(url, new=2))
        except Exception:
            ok = False

        try:
            status = self._get_status_label()
        except Exception:
            status = None

        if ok:
            if status is not None:
                status.configure(text="Opened repo")
        else:
            try:
                self._root.clipboard_clear()
                self._root.clipboard_append(url)
            except Exception:
                pass
            if status is not None:
                status.configure(text="Couldn't open browser (URL copied)")

        if status is not None:
            self._root.after(2000, lambda: status.configure(text=""))
