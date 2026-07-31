# Security Policy

## Supported Version

This project is maintained as a personal learning project. There are no
official version releases — the current state of the `main` branch is
considered the version to evaluate.

| Version | Supported |
|---------|-----------|
| main    | ✅        |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**
A public issue makes the vulnerability visible to everyone before it can be
fixed.

Instead, please use GitHub's private reporting feature:
**Security → Report a vulnerability** (tab at the top of the repository) —
this creates a private security advisory visible only to you and the
maintainer.

Please include in your report:

- Affected file(s)/endpoint(s)
- Steps to reproduce
- Potential impact (e.g. auth bypass, SQL injection, data leak)

## Known Design Decisions (not a bug)

- The JWT token is kept in `localStorage` on the frontend (not an `HttpOnly`
  cookie) — a deliberate design choice for this homelab setup.
- `FINNHUB_API_KEY` and `DISCORD_WEBHOOK_URL` are optional; without them, the
  corresponding features simply return empty results instead of an error.

## Not a Recommendation Tool

Security reports here refer strictly to technical aspects (auth, injection,
secrets handling, etc.), not to the correctness of the scoring output itself —
see the disclaimer in the [README](README.md).
