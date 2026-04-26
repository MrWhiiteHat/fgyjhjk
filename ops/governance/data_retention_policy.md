# Data Retention Policy

## Scope
Applies to application logs, audit logs, model artifacts, generated reports, temporary uploads, and backups.

## Retention Rules
- Application logs: retain 14 days.
- Audit logs: retain 180 days (minimum).
- Drift/monitoring reports: retain 60 days.
- Temporary upload/intermediate files: retain 24 hours.
- Deployment history and model metadata: retain indefinitely unless superseded by legal policy.
- Backups: retain according to backup policy tiers (daily/weekly/monthly).

## Deletion and Purge
- Automated purge jobs run on a schedule.
- Dry-run mode required before rule changes.
- Purges must remain within approved root directories.
- Purge summaries are logged and auditable.

## Compliance Hold
When legal/compliance hold is declared, automated deletion for relevant assets is suspended.
