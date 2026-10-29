# Keith Agent

Keith Agent is a collection of PowerShell and Python tools
for local automation, operational monitoring, backup
management, rollback, and controlled filesystem cleanup.

## Project status

Development source and historical versions.
Not independently certified for production use.

## Components

- cli-fix: Main Keith Agent CLI and patching tools.
- operations-v2: Backup, watchdog, scheduled-task
  installation, and job maintenance utilities.
- rollback-v1: Quarantine rollback tools.
- autopilot-v1: Original safe-autopilot implementation.
- autopilot-v2: Revised autopilot implementation.
- autopilot-v3: Expanded cleanup policy and protections.

## Security

The repository does not intentionally include credentials,
environment files, backup archives, or runtime data.

Existing scripts may contain machine-specific configuration
and network endpoints. Review these before deployment.

## Operational precautions

Some scripts can schedule tasks, launch processes,
remove old backup files, or move files into quarantine.

Do not execute installers or cleanup scripts without
reviewing their configuration and testing them in an
isolated environment.

## License

No open-source license has been granted.
All rights reserved.
