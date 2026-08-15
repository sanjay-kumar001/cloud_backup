# Cloud Backup — Core Runtime Patch Inventory

> **2026-08-10** — Scaffolded ahead of implementation (referenced by
> [`PROJECT_ROADMAP.md`](PROJECT_ROADMAP.md) §8 and `.claude/skills/backend-rules/SKILL.md`). This is the
> single source of truth for every runtime modification Cloud Backup makes to Frappe/ERPNext core — the
> patch inventory required by the patching handbook ([`patching_handbook.md`](patching_handbook.md),
> Appendix E, Ch. 38). Format follows that handbook's template.
>
> **Policy:** monkey-patching core is **banned** in Cloud Backup except for the entries listed here. Any
> new entry requires the handbook decision tree first
> (`doc_events` → `override_doctype_class` → `override_whitelisted_methods` → patch), a §2-style decision
> trail, **and** an update to this file **in the same commit**.
>
> **Status of this document:** the one entry below is **ACTIVE** as of 2026-08-11 — implemented in
> `cloud_backup/overrides/` and verified end-to-end (a `bench backup` auto-uploads to Drive and records a
> Cloud Backup History row). This file remains the governing contract.

---

## Index

1. [Inventory Summary](#1-inventory-summary)
2. [`post_backup_upload` — Backend: `frappe.utils.backups.new_backup`](#2-post_backup_upload--backend-frappeutilsbackupsnew_backup)
3. [Registration Coverage Matrix](#3-registration-coverage-matrix)
4. [Upgrade Audit Checklist](#4-upgrade-audit-checklist)
5. [Verification Procedures](#5-verification-procedures)
6. [Rollback](#6-rollback)
7. [How to Add a New Patch](#7-how-to-add-a-new-patch)

---

## 1. Inventory Summary

| Key | Side | Target | Registration | Risk | Status |
|---|---|---|---|---|---|
| `post_backup_upload` | Backend (Python) | `frappe.utils.backups.new_backup` | import-time + `before_request` + `before_job` + `after_migrate` | **LOW–MEDIUM** (backup path; additive, exception-fenced) | **Active** |

**Exactly one** core patch is planned. Everything else Cloud Backup layers onto core uses declarative
mechanisms: whitelisted API methods (`cloud_backup/api/*.py`), `scheduler_events` (daily retention cleanup;
`all` fallback poller), `frappe.enqueue` background jobs, fixtures (Role, permissions), and Frappe's own
`GoogleOAuth` + `Google Settings`. No DocType-controller override or `doc_events` patch is required.

**Naming.** The patch is keyed by what the wrap does (`post_backup_upload`), not a coined serial — matching
the project convention of no invented `XX-NNN` identifiers.

---

## 2. `post_backup_upload` — Backend: `frappe.utils.backups.new_backup`

```yaml
Key:             post_backup_upload  (keyed by behaviour — no coined serial)
Side:            Backend (Python)
Target:          frappe.utils.backups.new_backup  (module-level function)
Signature:       new_backup(older_than=6, ignore_files=False, ...) -> BackupGenerator
Patch module:    cloud_backup/overrides/core/backups.py  (apply_patches)
Registration:    PATCH_REGISTRY -> patch_manager -> import-time + before_request + before_job + after_migrate
Sentinel:        _cloud_backup_new_backup_patched  (attribute on the frappe.utils.backups module)
Business reason: Give a single, uniform "backup completed" hook. Every backup path — Desk
                 Download Backups, `bench backup`, and the daily cron — funnels through
                 new_backup, which returns the BackupGenerator (backup_path_db /
                 backup_path_files) only after the files exist on disk. Wrapping it enqueues
                 the cloud upload immediately, across all paths, with no core file edit (FR-07).
Risk level:      LOW–MEDIUM — runs on every backup, but is additive and exception-fenced;
                 the core return value is never altered.
Owner:           Cloud Backup maintainer (Sanjay Kumar)
Frappe tested:   v16
```

### Why a patch (handbook Ch.2 / Ch.4 last-resort criteria)

Frappe exposes **no** "backup completed" event. Tracing the call graph
(`frappe/utils/backups.py`, `frappe/desk/page/backups/backups.py`):

- **CLI** `bench backup` → `backup()` → `scheduled_backup()` → `new_backup()`
- **Cron** (scheduler) → `scheduled_backup()` → `new_backup()`
- **Desk** `schedule_files_backup` (whitelisted) → *enqueued* `backup_files_and_notify_user` → `backup()` → `scheduled_backup()` → `new_backup()`

Decision tree:

| Level | Mechanism | Applies? |
|---|---|---|
| 1 | `doc_events` | ✗ — backups are not a document lifecycle |
| 2 | `override_doctype_class` | ✗ — `new_backup` is not a DocType controller |
| 3 | `override_whitelisted_methods` | ✗ — the only whitelisted seam (`schedule_files_backup`) fires at *enqueue* time, **before the backup file exists** |
| 4 | **Runtime monkey-patch** | ✓ — `new_backup` is the sole post-file seam common to all three paths; no declarative hook reaches it |

Because `scheduled_backup` / `backup` resolve `new_backup` from the module global at call time, a **single**
module-level reassignment is picked up by every caller.

### What the wrapper does

1. Calls the **original** `new_backup(*args, **kwargs)` first — native backup behavior preserved verbatim;
   captures the returned `odb` (BackupGenerator).
2. When `Cloud Backup Settings.enabled && automatic_upload`, hands `odb.backup_path_db` /
   `odb.backup_path_files` to `cloud_backup.services.backup_service.enqueue_upload` (which creates the
   History row and `frappe.enqueue`s the upload).
3. **Returns `odb` unchanged.** Never mutates the return value.
4. The Cloud Backup step is wrapped in `try/except` + `frappe.log_error` — an upload-enqueue failure never
   breaks a core backup.

### Safety properties (handbook Ch.17–18)

| Handbook rule | Implementation |
|---|---|
| Idempotency | Module-level sentinel `_cloud_backup_new_backup_patched`; repeat `apply_patches` is a no-op |
| Original preserved | Captured in closure; always invoked first; return value passed through |
| Signature drift | Wrapper takes `*args, **kwargs`; `apply_patches` verifies `new_backup` exists before wrapping and logs + skips if the layout changed |
| Failure isolation | Upload-enqueue exception-fenced; logged to Error Log; core backup unaffected |
| Multi-worker | Sentinel is per-process memory — each web/RQ worker patches itself once (expected) |
| Secrets | Provider tokens/secrets never touched here; nothing sensitive logged |
| Commit-before-enqueue | `backup_service._create_and_enqueue` **commits the History row before `frappe.enqueue`**. The `bench backup` CLI process does not auto-commit like a web request, so without this the worker hits `DoesNotExistError` on the not-yet-committed row. Verified fix. |

---

## 3. Registration Coverage Matrix

Every seam funnels into `cloud_backup.overrides.patch_manager.apply_all_patches` (kill-switch → registry
loop → per-patch try/except → one-time log; originals recorded in `patch_manager._ORIGINALS`).

- **Import-time (primary, unconditional).** Called at the bottom of `cloud_backup/__init__.py`, so it runs
  the moment the `cloud_backup` package is imported — in every process. The wrap is site-independent
  (module-function reassignment), so no site is required; the kill-switch is read when `frappe.conf` is
  available and fenced against pre-init import.
- **`before_request` + `before_job` + `after_migrate`** (`hooks.py`) — self-healing idempotent retries for
  web ops, queued jobs, and post-migrate; also cover a failed early import-time apply.

| Context | Patched? | Verified via |
|---|---|---|
| Desk / web request | ✔ import-time (+ `before_request`) | `patch_status` → `sentinel: true` |
| REST API (`/api/method/*`) | ✔ import-time (+ `before_request`) | same |
| RQ worker / scheduler job (incl. cron backup) | ✔ import-time (+ `before_job`) | worker probe |
| `bench console` | ✔ import-time | console probe |
| `bench execute` | ✔ import-time | `bench execute …patch_status` |
| `frappe.enqueue(..., now=True)` | ✔ in-process | inline probe |
| `bench backup` (CLI) | ✔ import-time | file uploaded + History row |
| `bench migrate` / site-less CLI | ✔ import-time (harmless; kill-switch simply unread pre-init) | migrate clean |

---

## 4. Upgrade Audit Checklist

Run on **every** Frappe pull, before deploying (handbook Ch. 38):

### `post_backup_upload`
- [ ] `from frappe.utils import backups` imports cleanly.
- [ ] `hasattr(backups, "new_backup")` and it still **returns** the `BackupGenerator`.
- [ ] `odb` still exposes `backup_path_db` / `backup_path_files` / `backup_path_private_files`.
- [ ] `scheduled_backup` and `backup` still resolve `new_backup` via the module global (so one wrap covers
      all callers) — re-read `frappe/utils/backups.py` diff on major bumps.
- [ ] `inspect.signature(backups.new_backup)` reviewed; wrapper's `*args, **kwargs` still forwards cleanly.
- [ ] Console scenario re-run (see §5): CLI backup + Desk backup both produce a History row and a cloud
      file; kill-switch path falls back to the `all` poller.

Handbook risk grading: patch review mandatory on any minor bump, full re-validation on major bumps
(v16 → v17).

---

## 5. Verification Procedures

### Is the patch active? — `patch_status`

The applier runs at package import, so the patch is already on in any process.

```bash
bench --site test.local execute cloud_backup.overrides.patch_manager.patch_status
```
```python
# console
from cloud_backup.overrides.patch_manager import patch_status
print(patch_status())
```

Expected (illustrative):

```json
{"disabled": false,
 "originals": ["frappe.utils.backups.new_backup"],
 "target_exists": true, "sentinel": true}
```

- **`sentinel: true`** — patch applied (the field to check).
- **`originals`** — the core callable that was wrapped (recorded in `patch_manager._ORIGINALS`).
- **`disabled`** — `disable_runtime_patches` kill-switch state (site_config).
- **`target_exists`** — `frappe.utils.backups.new_backup` still present (guards a version rename).

### End-to-end (the test that matters)

1. Configure + authorize a provider, pick a `destination_folder`, set `enabled` + `automatic_upload`.
2. `bench --site test.local backup` (CLI path) → a `Cloud Backup History` row appears and the file lands in
   the provider's `destination_folder`.
3. Trigger the Desk *Download Backup* button → same outcome (Desk path).
4. Set `"disable_runtime_patches": 1` in `site_config.json` + restart → `patch_status.sentinel` is `false`;
   the `scheduler_events["all"]` fallback poller still uploads new backups (next tick).

Durable guards live in `cloud_backup/tests/test_core_patches.py` (target-exists, signature-stable,
sentinel, idempotency, kill-switch roundtrip, upload-path smoke) — write them with the patch (Phase 4).

---

## 6. Rollback

| Step | `post_backup_upload` |
|---|---|
| Immediate (no deploy) | Set `"disable_runtime_patches": 1` in `site_config.json` + restart workers — the kill-switch at the top of `apply_all_patches` skips the whole registry; the `all` fallback poller sustains auto-upload |
| In-process (console) | `from cloud_backup.overrides.patch_manager import _ORIGINALS` → restore the recorded original onto `frappe.utils.backups.new_backup` and clear the module sentinel |
| Code-level | Remove the entry from `patch_registry.py` + restart. The original `new_backup` is untouched core code — new processes start vanilla |
| Data | None. Backups and History rows already written are unaffected; only *future* auto-upload stops (manual upload + CLI still work) |

---

## 7. How to Add a New Patch

The register must stay at **one** entry unless a new BRD requirement forces another. To add one:

1. **Exhaust the decision tree first** (`doc_events` → `override_doctype_class` →
   `override_whitelisted_methods`). Only patch when none apply — and record *why* in a §2-style block.
2. Add the target module under `cloud_backup/overrides/core/<core_module>.py` with an idempotent
   `apply_patches()` (existence guard, `record_original`, sentinel, call-original-first, exception-fence).
3. Register its dotted `apply_patches` in `cloud_backup/overrides/patch_registry.py`.
4. Add an Inventory Summary row + a full §2 section + Upgrade Audit + Rollback entries **in the same
   commit** (SKILL.md governance).
5. Write upgrade-guard tests in `cloud_backup/tests/test_core_patches.py`.

---

*References: [`patching_handbook.md`](patching_handbook.md) (esp. Ch. 13–18, Appendix D–E) ·
[`PROJECT_ROADMAP.md`](PROJECT_ROADMAP.md) §8 · reference implementation:
`avian/avian/overrides/{patch_manager,patch_registry}.py`.*
