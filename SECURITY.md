# Security Policy

This is the canonical security policy for KeyRGB.

## Supported Versions

KeyRGB is maintained on a best-effort basis.

- The latest tagged release is the primary supported path.
- The current `main` branch may also receive fixes before the next release.
- Older releases may not receive backported security fixes.

## Reporting a Vulnerability

If you believe you found a security issue:

- Prefer private reporting through GitHub Security Advisories, if enabled for the repository.
- If that is not available, contact the maintainer privately through GitHub rather than opening a public issue first.
- Include the affected version or commit, distro, hardware path, reproduction steps, expected impact, and whether the issue requires local access.

Please avoid posting working exploit details in a public issue before the maintainer has had a chance to review the report.

## Notes

- KeyRGB interacts with USB and hidraw devices and may write user configuration under `~/.config/keyrgb/`.
- Avoid running KeyRGB as root unless you are explicitly debugging permissions or using installer-managed privileged helpers.
