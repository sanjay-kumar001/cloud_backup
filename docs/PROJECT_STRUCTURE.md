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
├── hooks.py                         # single wiring surface (fixtures; more added later)
├── fixtures/
│   └── role.json                    # Cloud Backup Manager role
├── cloud_backup/                    # module "Cloud Backup"
│   └── doctype/
│       ├── cloud_backup_settings/   # Single — global settings
│       ├── cloud_backup_provider/   # provider config + credentials
│       └── cloud_backup_log/        # operational event log
├── api/
│   └── provider.py                  # whitelisted: authorize, test_connection, list/create folders
├── services/
│   ├── oauth_service.py             # drive-domain registration, authorize URL, callback, token refresh
│   └── provider_service.py          # resolve authed provider instance (+ token refresh) via registry
├── providers/
│   ├── base.py                      # CloudBackupProvider ABC (BRD §9.1 contract)
│   ├── registry.py                  # provider_type -> class resolver (google_drive registered)
│   └── google_drive/
│       ├── __init__.py              # drive OAuth wiring constants
│       └── provider.py              # GoogleDriveProvider (auth, test, folders, quota)
├── utils/
│   ├── constants.py                 # provider-type enum + storage-kind map (single source of truth)
│   └── exceptions.py                # typed error taxonomy (BRD §12)
└── tests/
    ├── test_providers.py            # ABC / registry / exception unit tests
    ├── test_google_drive_provider.py# Drive provider (API stubbed)
    └── test_provider_service.py     # token-refresh orchestration + oauth wiring
```

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
  DocTypes; all credential/token persistence lives in `services/`. Upload/list/delete of files are stubbed
  (`NotImplementedError`) until the upload milestone.

## Delivered DocTypes

| DocType | Type | Purpose | Key fields |
|---|---|---|---|
| Cloud Backup Settings | Single | Global config | `enabled`, `default_provider`, `automatic_upload`, upload-type checks, `verify_upload`, `notifications_enabled`, `auto_delete_remote`, `retention_type`/`retention_count`/`retention_days`, read-only status + cleanup trios |
| Cloud Backup Provider | Master | Provider config + credentials | `provider_name`, `provider_type`, `enabled`, `authentication_status`, `Password` secrets, `token_expiry`, `root_folder`/`destination_folder`/`folder_name_display`, `bucket`/`region` |
| Cloud Backup Log | Master (in-create) | Technical events | `timestamp`, `level`, `event`, `source`, `message`, `details` |

## Roles & Permissions

- **Cloud Backup Manager** (fixture): read/write/create/delete on Provider; read/write on Settings; read on
  Log. **System Manager**: full on all three (delete on Log).

## Provider Abstraction

- `providers/base.py::CloudBackupProvider` (ABC) freezes the §9.1 contract: `authenticate`,
  `test_connection`, `list_folders`, `create_folder`, `upload_file`, `list_files`, `get_file_metadata`,
  `delete_file`, `get_storage_usage`. No implementations yet (Phase 2+). Reserves the `provider_type` /
  `storage_kind` class attributes so providers self-classify.
- `providers/registry.py::PROVIDER_REGISTRY` maps `provider_type` → class; empty until Google Drive lands.

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
