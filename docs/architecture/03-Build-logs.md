# Build logs

`buildpython` writes a log file per step to help with debugging CI failures and reviewing PRs.

## Location

Logs are written to:

- `buildlog/keyrgb/`

This directory is ignored by git.

## Format

Each step log uses a standardized, machine-parsable format:

```
=== Step Name - 2025-12-25T12:34:56.789Z ===
Command: command-that-was-run
Duration: (X.Xs)
Exit Code: N

=== STDOUT ===
(stdout content or "(no stdout)")

=== STDERR ===
(stderr content or "(no stderr)")

=== END ===
```

## When to request logs

When troubleshooting an issue or reviewing a PR, ask for:

- The failing step’s log file from `buildlog/keyrgb/`
- The command that was run (already recorded in the log)
- OS + Python version

This reduces “works on my machine” back-and-forth.
