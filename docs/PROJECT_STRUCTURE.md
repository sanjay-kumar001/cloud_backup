# Cloud Backup — Project Structure

**Authority:** This is the living file-layout reference. It wins file-layout conflicts once populated
(supersedes `PROJECT_ROADMAP.md` §2). Update in the same commit whenever DocTypes or packages are
added/renamed.

## Package Layout

DocType controllers live in the module directory (`cloud_backup/cloud_backup/doctype/…`, standard Frappe).
Supporting Python packages sit at the app-root package (`cloud_backup/<pkg>/`) and are imported by dotted
path (`cloud_backup.providers.base`, etc.).

```text
cloud_backup/
├── __init__.py                      # import-time bootstrap: apply governed core patches
├── hooks.py                         # wiring: before_request/before_job/after_migrate, scheduler_events
├── tasks.py                         # scheduler entrypoints: auto_upload_fallback, run_due_schedules
├── commands/                        # bench cloud-backup CLI (click group)
├── cloud_backup/                    # module "Cloud Backup"
│   └── doctype/
│       ├── cloud_backup_settings/   # Single — global settings
│       ├── cloud_backup_provider/   # provider config + credentials
│       ├── cloud_backup_log/        # operational event log
│       ├── cloud_backup_history/    # one row per upload attempt (in-create)
│       └── cloud_backup_schedule/   # recurring backup-and-upload cadence
├── api/
│   ├── provider.py                  # whitelisted: authorize, test_connection, list/create folders
│   └── backup.py                    # whitelisted: upload_latest (validate + enqueue)
├── overrides/                       # governed core runtime patch framework (docs/CORE_PATCHES.md)
│   ├── patch_manager.py             # apply_all_patches, kill-switch, record_original, patch_status
│   ├── patch_registry.py            # PATCH_REGISTRY tuple of dotted apply-callables
│   └── core/backups.py              # wraps frappe.utils.backups.new_backup (post-backup auto-upload)
├── services/
│   ├── oauth_service.py             # drive-domain registration, authorize URL, callback, token refresh
│   ├── provider_service.py          # resolve authed provider instance (+ token refresh) via registry
│   ├── backup_service.py            # find latest backup, create History, enqueue upload (+ auto/schedule)
│   ├── retention_service.py         # Settings-gated cloud cleanup (managed rows only, count/age)
│   ├── notification_service.py      # in-app + email to System Managers on key events
│   └── log_service.py               # write Cloud Backup Log rows with secrets scrubbed
├── jobs/
│   ├── upload_backup.py             # enqueued entrypoint: upload one artifact (retry + verify)
│   └── cleanup_backup.py            # scheduled/manual retention cleanup entrypoint
├── providers/
│   ├── base.py                      # CloudBackupProvider ABC (BRD §9.1 contract)
│   ├── registry.py                  # provider_type -> class resolver (google_drive registered)
│   └── google_drive/
│       ├── __init__.py              # drive OAuth wiring constants
│       └── provider.py              # GoogleDriveProvider (auth, test, folders, quota, resumable upload)
├── utils/
│   ├── constants.py                 # DocType names, provider-type enum + storage-kind map, upload consts
│   ├── file_utils.py                # pure filename helpers (remote name, extension, slug)
│   └── exceptions.py                # typed error taxonomy (BRD §12)
└── tests/
    ├── test_providers.py            # ABC / registry / exception unit tests
    ├── test_google_drive_provider.py# Drive provider (API stubbed)
    ├── test_provider_service.py     # token-refresh orchestration + oauth wiring
    ├── test_file_utils.py           # filename helpers
    ├── test_upload.py               # enqueue_upload + upload job (Drive mocked)
    ├── test_core_patches.py         # governed patch upgrade guards
    ├── test_schedules.py            # schedule due-evaluation + per-provider dedupe
    └── test_reliability.py          # secret scrubbing + retention selection/safety
```

**Naming constants:** DocType names live once in `utils/constants.py::DocType` (`DocType.PROVIDER`, etc.)
and are imported across services/api/jobs — no repeated name literals in Python. (Schema JSON still declares
the names, as Frappe requires.)

## Google Drive Authentication (OAuth)

Uses Frappe's `GoogleOAuth` and its **shared callback** (`frappe.integrations.google_oauth.callback`), per
core convention — no core files edited. Because the `drive` domain is not pre-registered in core,
`oauth_service.register_drive_domain()` maps it to this app's callback + service version; it is wired on
`before_request`/`before_job` (hooks.py) so the shared callback resolves it in web and worker processes.

- **Authorize:** form button → `api.provider.authorize` → `oauth_service.get_authorization_url` (state
  carries the provider name + redirect back to the form) → Google consent → shared callback →
  `oauth_service.authorize_access` exchanges the code and stores `access_token`/`refresh_token`/
  `token_expiry` (Password fields) and flips `authentication_status` to Authorized.
- **Token refresh:** `provider_service.get_provider` refreshes an expired Drive token via
  `GoogleOAuth.refresh_access_token` before use; on refresh failure it sets `authentication_status = Expired`.
- **Folder browser:** form dialog drives `api.provider.list_folders` / `create_folder`; selection writes
  `destination_folder` + `folder_name_display` on the Provider (the upload target the engine reads later).
- **Boundary note:** `GoogleDriveProvider` (in `providers/`) does pure Drive I/O and never writes app
  DocTypes; all credential/token persistence lives in `services/`.

## Manual Upload → Google Drive

- **Trigger:** Settings form **Upload Latest Backup** → `api.backup.upload_latest` validates config (default
  provider set, Authorized, destination chosen) → `backup_service.enqueue_upload`.
- **Discovery:** `backup_service.find_latest_backup` wraps `frappe.utils.backups.fetch_latest_backups()`
  (System Manager operator). One **Cloud Backup History** row (`Queued`) is created per artifact
  (`database` → db; `files` → public+private; `full` → all), then `frappe.enqueue`'d on the `long` queue.
- **Job:** `jobs/upload_backup.run` walks the row `Processing → Uploading → Completed/Failed`, persisting
  and committing each transition (survives worker crash, NFR-17). It builds the remote name
  `{site}_{label}_{YYYYMMDD_HHMMSS}{ext}` (`utils/file_utils`), uploads via the provider's **resumable**
  `upload_file` into the provider's `destination_folder`, records `remote_file`/`size`/`checksum`, and
  writes the `last_upload_*` trio back onto Settings. Live status is pushed via `publish_realtime`.
- **Verification (P5):** `verification_status` and `retry_count` fields exist but are not yet driven.

## Automatic & Scheduled Upload

- **Post-backup auto-upload (the one core patch).** `overrides/core/backups.py` wraps
  `frappe.utils.backups.new_backup` (governed by [CORE_PATCHES.md](CORE_PATCHES.md)): every backup path
  (Desk / `bench backup` / cron) funnels through it, so after the files exist it calls
  `backup_service.enqueue_after_backup(odb)` — Settings-gated (`enabled` + `automatic_upload`), uploads the
  selected artifacts to `Settings.default_provider`. Applied via import-time bootstrap +
  `before_request`/`before_job`/`after_migrate`; kill-switch `disable_runtime_patches`; probe
  `patch_manager.patch_status()`.
- **Fallback poller.** `scheduler_events["all"] → tasks.auto_upload_fallback` acts **only** when the patch is
  kill-switched off, polling `fetch_latest_backups()` so auto-upload still works (next-tick latency).
- **Schedules.** `tasks.run_due_schedules` (scheduler `all`) runs each enabled **Cloud Backup Schedule**
  whose cadence is due (`is_due`: Daily/Weekly by `last_run`, Custom by croniter), calling `new_backup` then
  `backup_service.enqueue_for_schedule` to upload to *that schedule's* provider. **Run Now** button on the
  form triggers it on demand.
- **Dedupe (NFR-06).** `already_uploaded(path, provider)` keys on **(local file, provider)**, so the patch
  and the fallback/schedule never double-upload the same artifact to the same provider; different providers
  are treated as distinct destinations.
- **Commit-before-enqueue.** `_create_and_enqueue` commits the History row before `frappe.enqueue` — the CLI
  backup process doesn't auto-commit like a web request, so the worker would otherwise miss the row.
- **Backup types are single-source.** Only **Settings** carries `upload_database`/`upload_files`/
  `upload_full`; the auto-path, the fallback, and every **Schedule** read them via
  `backup_service.selected_artifacts`. A Schedule defines only *when* + *which provider*.

## Reliability (retry · verify · retention · notify)

- **Retry.** `jobs/upload_backup._upload_with_retry` retries **retryable** errors (`NetworkError`/
  `RateLimited`/429/5xx) with exponential backoff (2→5→10s, max 4 attempts), incrementing `retry_count` and
  flipping status to `Retrying`; honours `RateLimited.retry_after`. Non-retryable errors fail immediately.
  History exposes a manual **Retry Upload** button (`api.backup.retry_upload`).
- **Verification.** When `Settings.verify_upload`, `_verify` compares remote size (and checksum when both
  sides expose one) via `provider.get_file_metadata` → `verification_status` Verified/Failed.
- **Retention (safety-critical).** `retention_service.run_cleanup` is gated by `Settings.auto_delete_remote`
  and drives deletion **from Cloud Backup History rows only** — never by enumerating the remote folder — so
  unrelated files can't match (FR-20/38). Per provider it applies count- or age-based policy, calls
  `provider.delete_file`, marks the row `remote_deleted`, and writes `last_cleanup_*`. Wired
  `scheduler_events["daily"] → jobs.cleanup_backup.run`; **Run Cleanup Now** button + `api.backup.run_cleanup`
  (with `dry_run`). Idempotent (NFR-14).
- **Notifications.** `notification_service.notify` sends in-app + email to enabled System Managers on
  failures when `Settings.notifications_enabled`.
- **Logging.** `log_service.write_log` records events to **Cloud Backup Log** with secrets scrubbed
  (`scrub_secrets` redacts token/secret/password/client_id keys and masks token-like strings, NFR-10/34).

## CLI (`bench cloud-backup`)

`commands/__init__.py` registers a `click` group (discovered via `<app>.commands.commands`) that reuses the
Phase 3–5 services — no logic duplication. Uploads run **synchronously** (`backup_service.upload_artifacts_sync`)
so exit codes reflect the real result (FR-55).

- `bench --site <s> cloud-backup [--with-files]` — create a backup + upload (db, or db+files).
- `... cloud-backup test` — provider connectivity (non-zero when broken).
- `... cloud-backup list [--limit N]` — recent History rows.
- `... cloud-backup cleanup` — run retention now.
- `... cloud-backup status` — provider, toggles, last-upload status, counts (non-zero if last upload failed).

## Delivered DocTypes

| DocType | Type | Purpose | Key fields |
|---|---|---|---|
| Cloud Backup Settings | Single | Global config | `enabled`, `default_provider`, `automatic_upload`, upload-type checks, `verify_upload`, `notifications_enabled`, `auto_delete_remote`, `retention_type`/`retention_count`/`retention_days`, read-only status + cleanup trios |
| Cloud Backup Provider | Master | Provider config + credentials | `provider_name`, `provider_type`, `enabled`, `authentication_status`, `Password` secrets, `token_expiry`, `root_folder`/`destination_folder`/`folder_name_display`, `bucket`/`region` |
| Cloud Backup Log | Master (in-create) | Technical events | `timestamp`, `level`, `event`, `source`, `message`, `details` |
| Cloud Backup History | Master (in-create) | One row per upload attempt | `site`, `provider`, `backup_type`, `local_file`/`local_file_size`, `status`, `started_at`/`completed_at`/`duration`, `remote_file`/`remote_path`/`file_size`/`checksum`, `verification_status`, `retry_count`, `error` |
| Cloud Backup Schedule | Master | Recurring backup-and-upload cadence | `schedule_name`, `enabled`, `provider`, `schedule_type` (Daily/Weekly/Custom), `frequency` (cron), `last_run` (backup **types** inherited from Settings) |

## Roles & Permissions

- **System Manager** only, on all DocTypes. Provider/Settings: read/write (+create/delete on Provider);
  Log/History: read + delete (system-generated, `in_create`).
- **Deviation from BRD §13 (owner-approved):** the BRD defines a dedicated **Cloud Backup Manager** role;
  it was dropped in favour of gating the whole app on **System Manager**. Backup/upload/restore are
  admin-level operations, and this removes the friction with `fetch_latest_backups()`
  (`frappe.only_for("System Manager")`). Re-introduce the role later if delegated, non-admin access is
  needed.

## Provider Abstraction

- `providers/base.py::CloudBackupProvider` (ABC) freezes the §9.1 contract: `authenticate`,
  `test_connection`, `list_folders`, `create_folder`, `upload_file`, `list_files`, `get_file_metadata`,
  `delete_file`, `get_storage_usage`. Reserves the `provider_type` / `storage_kind` class attributes so
  providers self-classify. `upload_file(local_path, remote_target, remote_name)` carries the destination and
  the built remote filename.
- `providers/registry.py::PROVIDER_REGISTRY` maps `provider_type` → class (`google_drive` implemented).

## Provider-Type Classification (single source of truth)

`utils/constants.py::PROVIDER_STORAGE_KIND` is the one canonical map of `provider_type → StorageKind`
(folder vs object); `FOLDER_PROVIDERS`/`OBJECT_PROVIDERS`/`PROVIDER_TYPES` derive from it. The Provider
DocType carries a hidden read-only `storage_kind` field (set in `validate`, kept live in the form via the
whitelisted `get_provider_storage_kind`), so section `depends_on` and the client script reference
`storage_kind`, never enumerated provider names. A parity test asserts the `provider_type` Select equals
`PROVIDER_TYPES`. Once providers are registered (Phase 2/7), this map derives from the registry and the
hand-maintained dict retires — see roadmap Phases 2 & 7.

## Boundary Rule

Anything that calls `frappe.get_doc/.save/.submit` lives in a DocType controller or (later) `services/` —
never in `providers/` (pure remote I/O) or `utils/` (pure helpers).
