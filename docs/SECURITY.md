# Security Policy

## Supported Versions

This project is provided on a best-effort basis. Security fixes are handled as time permits.

## Reporting a Vulnerability

If you believe you’ve found a security issue:

- Prefer private reporting via GitHub Security Advisories (if enabled on the repo), or by contacting the maintainer.
- Please include steps to reproduce, affected version/commit, and impact.

## Notes

KeyRGB interacts with USB hardware and writes user configuration files under `~/.config/keyrgb/`. Avoid running it as root unless you are debugging permissions.
