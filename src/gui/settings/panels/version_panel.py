from __future__ import annotations

import json
import webbrowser
from importlib import metadata
from threading import Thread
from typing import Callable
from urllib.request import Request, urlopen

import tkinter as tk
from tkinter import ttk

from src.core.version_check import compare_versions, normalize_version_text


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
                "Shows your installed KeyRGB version and checks GitHub to see\n"
                "whether you're on the latest tag."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 8))

        grid = ttk.Frame(parent)
        grid.pack(fill="x", pady=(0, 8))

        ttk.Label(grid, text="Installed", font=("Sans", 9)).grid(row=0, column=0, sticky="w")
        self.lbl_installed_version = ttk.Label(grid, text="?", font=("Sans", 9))
        self.lbl_installed_version.grid(row=0, column=1, sticky="w", padx=(10, 0))

        ttk.Label(grid, text="Latest", font=("Sans", 9)).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.lbl_latest_version = ttk.Label(grid, text="Checking…", font=("Sans", 9))
        self.lbl_latest_version.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(4, 0))

        self.lbl_update_status = ttk.Label(parent, text="", font=("Sans", 9))
        self.lbl_update_status.pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=(0, 2))

        self.btn_open_repo = ttk.Button(btn_row, text="Open repo", command=self._open_repo)
        self.btn_open_repo.pack(side="left")

        self._installed_version = self._installed_version_text()
        self.lbl_installed_version.configure(text=self._installed_version)
        self.lbl_latest_version.configure(text="Checking…")
        self.lbl_update_status.configure(text="")

        self.start_latest_version_check()

    def start_latest_version_check(self) -> None:
        def worker() -> None:
            latest = self._fetch_latest_github_tag()
            self._root.after(0, lambda: self._apply_latest_version_result(latest))

        Thread(target=worker, daemon=True).start()

    def _installed_version_text(self) -> str:
        try:
            v = metadata.version("keyrgb")
        except Exception:
            return "unknown"

        v_norm = normalize_version_text(v) or str(v).strip()
        return f"v{v_norm}" if not str(v).strip().lower().startswith("v") else str(v).strip()

    def _fetch_latest_github_tag(self) -> str | None:
        # Best-effort: releases can be behind, so prefer tags.
        urls = [
            "https://api.github.com/repos/Rainexn0b/keyRGB/tags?per_page=1",
            "https://api.github.com/repos/Rainexn0b/keyRGB/releases/latest",
        ]

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "keyrgb",
        }

        for url in urls:
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=3.0) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)

                if isinstance(data, list) and data:
                    first = data[0]
                    name = first.get("name") if isinstance(first, dict) else None
                    if isinstance(name, str) and name.strip():
                        return name.strip()

                if isinstance(data, dict):
                    tag_name = data.get("tag_name")
                    if isinstance(tag_name, str) and tag_name.strip():
                        return tag_name.strip()
            except Exception:
                continue

        return None

    def _apply_latest_version_result(self, latest_tag: str | None) -> None:
        if not latest_tag:
            self.lbl_latest_version.configure(text="Unknown")
            self.lbl_update_status.configure(text="Couldn't check GitHub")
            return

        latest_norm = normalize_version_text(latest_tag) or latest_tag
        latest_display = f"v{latest_norm}" if not str(latest_tag).lower().startswith("v") else str(latest_tag)
        self.lbl_latest_version.configure(text=latest_display)

        cmp = compare_versions(self._installed_version, latest_display)
        if cmp is None:
            self.lbl_update_status.configure(text="Couldn't compare versions")
        elif cmp == 0:
            self.lbl_update_status.configure(text="✓ You are on the latest version")
        elif cmp < 0:
            self.lbl_update_status.configure(text=f"Update available: {latest_display}")
        else:
            self.lbl_update_status.configure(text="You are ahead of the latest tag")

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
