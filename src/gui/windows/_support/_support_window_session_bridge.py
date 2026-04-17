#!/usr/bin/env python3

from __future__ import annotations

from . import _support_window_state as support_window_state


class SupportWindowSessionBridgeMixin:
    _support_session: support_window_state.SupportSessionState

    @staticmethod
    def _support_session_cls() -> type[support_window_state.SupportSessionState]:
        return support_window_state.SupportSessionState

    def _ensure_support_session(self) -> support_window_state.SupportSessionState:
        session_cls = self._support_session_cls()
        try:
            session = self._support_session
        except AttributeError:
            session = session_cls()
            self._support_session = session
            return session

        if isinstance(session, session_cls):
            return session

        session = session_cls()
        self._support_session = session
        return session

    @property
    def _diagnostics_json(self) -> str:
        return self._ensure_support_session().diagnostics_json

    @_diagnostics_json.setter
    def _diagnostics_json(self, value: str) -> None:
        self._ensure_support_session().diagnostics_json = str(value or "")

    @property
    def _discovery_json(self) -> str:
        return self._ensure_support_session().discovery_json

    @_discovery_json.setter
    def _discovery_json(self, value: str) -> None:
        self._ensure_support_session().discovery_json = str(value or "")

    @property
    def _supplemental_evidence(self) -> dict[str, object] | None:
        return self._ensure_support_session().supplemental_evidence

    @_supplemental_evidence.setter
    def _supplemental_evidence(self, value: dict[str, object] | None) -> None:
        self._ensure_support_session().supplemental_evidence = value

    @property
    def _issue_report(self) -> dict[str, object] | None:
        return self._ensure_support_session().issue_report

    @_issue_report.setter
    def _issue_report(self, value: dict[str, object] | None) -> None:
        self._ensure_support_session().issue_report = value

    @property
    def _capture_prompt_key(self) -> str:
        return self._ensure_support_session().capture_prompt_key

    @_capture_prompt_key.setter
    def _capture_prompt_key(self, value: str) -> None:
        self._ensure_support_session().capture_prompt_key = str(value or "")

    @property
    def _backend_probe_prompt_key(self) -> str:
        return self._ensure_support_session().backend_probe_prompt_key

    @_backend_probe_prompt_key.setter
    def _backend_probe_prompt_key(self, value: str) -> None:
        self._ensure_support_session().backend_probe_prompt_key = str(value or "")
