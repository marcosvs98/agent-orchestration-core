# Security policy

## Supported versions

Security fixes are applied to the **latest minor release** on the default branch (`main`). Older tags may not receive backports unless agreed explicitly.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for undisclosed security problems.

Instead, contact the maintainers through a **private channel** (for example security email or internal incident queue) with:

- A short description of the issue and impact
- Steps to reproduce (proof of concept if safe)
- Affected versions or commit range if known

We aim to acknowledge receipt within a few business days and coordinate disclosure after a fix is available.

## Dependency updates

Automated dependency updates (for example Dependabot) should be reviewed for supply-chain and compatibility risk before merge.

## Hardening

For container and runtime posture, follow internal checklists and the deployment notes under `docs/Deployment/`.
