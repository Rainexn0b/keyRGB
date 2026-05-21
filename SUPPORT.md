# Support

Use this document to choose the right support path before opening an issue.

## Start Here

- Read [README.md](README.md), especially the install, troubleshooting, and hardware-support sections.
- Run `keyrgb-diagnostics` and keep the JSON output ready.
- If the issue is runtime-related, also capture `KEYRGB_DEBUG=1 keyrgb` output.
- Stop other RGB tools or vendor daemons before reproducing the problem.

## Which Issue Path To Use

- New laptop, unknown controller, unsupported device, or new hardware evidence:
  use the **Hardware support / diagnostics** issue template.
- Problem on hardware that KeyRGB already partially or fully supports:
  use the **Bug report (supported hardware)** template.
- Experimental backend works on real hardware and you want it considered for promotion:
  use the **Experimental backend confirmation / promotion request** template.

Issue chooser:

- https://github.com/Rainexn0b/keyRGB/issues/new/choose

## Include This Information

- KeyRGB version or commit
- Distro, kernel, desktop environment, and Wayland or X11 session
- `keyrgb-diagnostics` output
- Relevant `lsusb` output for the controller
- Whether brightness, uniform color, per-key mode, or effects work
- Whether other RGB tools were running

## Security Reports

Do not use public issues for suspected security vulnerabilities. Follow [SECURITY.md](SECURITY.md) instead.

## Contribution Workflow

If you want to submit a fix or backend addition, see [CONTRIBUTING.md](CONTRIBUTING.md).
