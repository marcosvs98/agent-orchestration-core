# Security policy

## Supported versions

Security fixes are applied to the latest release on the default branch (`main`). Older tags do not
receive backports unless agreed explicitly.

## Reporting a vulnerability

**Do not open a public issue for an undisclosed security problem.**

Use GitHub's private vulnerability reporting on this repository — the *Report a vulnerability*
button under the Security tab. It creates a private thread visible only to you and the maintainers,
so there is no address to look up and nothing to encrypt.

Please include:

- What the issue is and what an attacker gets from it
- Steps to reproduce, with a proof of concept if it is safe to share one
- The affected versions or commit range, if you know them

You will get an acknowledgement within a few business days. Disclosure is coordinated after a fix
is available, and we will credit you unless you prefer otherwise.

## Known limitations

Some weaknesses are already documented rather than pending. Before reporting, check
[Known limitations](docs/Develop/limitations.md) — if what you found is listed there, it is known
and the trade-off is deliberate. Anything not listed there is worth reporting.

## Scope

In scope: this repository's source, its default configuration, and the deployment artefacts it
ships. Out of scope: findings that require a configuration the project explicitly documents as
unsafe, and the model providers, databases and brokers this service integrates with — report those
to their own maintainers.

## Dependency updates

Automated dependency updates are reviewed for supply-chain and compatibility risk before merge, not
merged on green alone.

## Hardening

Container and runtime posture is covered in [Docker deployment](docs/Deployment/docker.md). The API
documentation surfaces (`/docs`, `/redoc`, `/openapi.json`) are closed unless
`ENVIRONMENT=development` or `EXPOSE_API_DOCS` is set explicitly.
