# Security Policy

## Supported Versions

Knowledge Engine Core is pre-release software. Security fixes will target the
latest version on `main` until the first stable release policy is defined.

## Reporting a Vulnerability

Please do not report security vulnerabilities in public issues.

Until a private security contact is published, prepare a concise report with:

- Affected version or commit.
- Steps to reproduce.
- Impact.
- Any known workaround.
- Whether the issue involves private data, unsafe file handling, or command
  execution.

Once the repository is published on GitHub, enable private vulnerability
reporting and update this file with the official reporting path.

## Scope

Security-sensitive areas include:

- PDF parsing and file handling.
- Path traversal or unsafe filesystem writes.
- SQLite database handling.
- Future ingestion of external metadata.
- Future worker, API, AI, OCR, and graph integrations.

## Current Limitations

Phase 0 is a local offline application. It does not run a network service and
does not process untrusted files in a sandbox. Treat PDFs as untrusted inputs and
only import files from sources you trust.
