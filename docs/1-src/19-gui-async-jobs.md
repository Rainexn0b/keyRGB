# GUI async jobs

Status: **Done**

## Purpose

Tk callbacks must stay off the hardware and OS path. Background GUI work needs
an explicit generation so a newer click or preview tick can discard a stale
result.

## Contract

`keyrgb/gui/utils/tk_async.py` owns the worker helper:

| API | Role |
|---|---|
| `TkAsyncJob` | Cancel handle plus generation |
| `TkAsyncCoordinator.submit()` | Cancel the previous job, then start a newer generation |
| `run_in_thread()` | One-shot worker; still used by settings/support |
| `submit_gui_work()` | Uses `owner.tk_jobs` when a live Tk root exists; otherwise runs inline |

Cancelled or superseded jobs never invoke `on_done`. The worker may still finish
a USB/sysfs call already in flight; only the UI delivery is suppressed.

## Window owners

Production windows create `tk_jobs = TkAsyncCoordinator()` and submit:

- Uniform color apply/release hardware writes
- Power-mode live frequency preview and save/reapply
- Per-key editor hardware commit

Unit tests that construct windows with `__new__` or `SimpleNamespace` have no
coordinator, so they keep the previous synchronous callback contract.

## Non-goals

- Aborting an in-flight HID report
- Making every Tk `after()` timer a background job
- Changing public GUI entrypoints
