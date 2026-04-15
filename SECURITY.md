# Security

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately to the maintainers (e.g. GitHub **Security** → *Report a vulnerability*, or an email listed in the repository profile once published).

Include:

- Description and impact
- Steps to reproduce
- Affected versions / commits (if known)

## General practices

- Never commit API keys, Auth0 secrets, FGA client secrets, or database files with real user data.
- Rotate credentials immediately if they are exposed.
- This repository is a **demo**: simulated commerce data and in-memory stores are not suitable for production as-is.

## Dependency updates

Keep `backend/pyproject.toml` and `frontend/package.json` dependencies reasonably current; review changelogs for breaking security fixes.
