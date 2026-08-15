# Cloud Backup — User Guide

Automated cloud backup upload for Frappe / ERPNext. This guide takes you from a fresh install to a
verified, scheduled, self‑cleaning backup pipeline on the cloud provider of your choice.

---

## Index

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Part A — Set up the Cloud Backup app](#3-part-a--set-up-the-cloud-backup-app)
   - [3.1 Install & enable](#31-install--enable)
   - [3.2 Create a Provider record](#32-create-a-provider-record)
   - [3.3 Authorize / enter credentials](#33-authorize--enter-credentials)
   - [3.4 Select the destination folder / prefix](#34-select-the-destination-folder--prefix)
   - [3.5 Configure Cloud Backup Settings](#35-configure-cloud-backup-settings)
   - [3.6 Add a Schedule (optional)](#36-add-a-schedule-optional)
4. [Part B — Provider‑side setup](#4-part-b--providerside-setup)
   - [4.1 Google Drive](#41-google-drive)
   - [4.2 Dropbox](#42-dropbox)
   - [4.3 Microsoft OneDrive](#43-microsoft-onedrive)
   - [4.4 Amazon S3](#44-amazon-s3)
5. [Retention policy](#5-retention-policy)
6. [Fallback provider](#6-fallback-provider)
7. [Verification](#7-verification)
8. [Notifications & quota warnings](#8-notifications--quota-warnings)
9. [Command line (CLI)](#9-command-line-cli)
10. [Restore](#10-restore)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

Cloud Backup connects Frappe's native backup mechanism to cloud object/file storage. You configure one or
more **providers**, choose a **default** (and optional **fallback**), and then backups are uploaded either
automatically (after every `bench backup`), on a **schedule**, or on demand. Uploads are verified, recorded
in **Cloud Backup History**, and pruned by a **retention policy**.

Four providers are supported today:

| Provider | Kind | Credentials you create | Console |
| --- | --- | --- | --- |
| Google Drive | Folder | OAuth Client ID + Secret | Google Cloud Console |
| Dropbox | Folder | App key + App secret | Dropbox App Console |
| Microsoft OneDrive | Folder | Application (client) ID + Secret | Azure Portal |
| Amazon S3 | Object (bucket) | Access Key ID + Secret Access Key | AWS IAM |

---

## 2. Prerequisites

- Frappe / ERPNext **v16+** on Python **3.14+**.
- Redis and a **running worker** (`bench start`, or a supervised `bench worker`) — uploads run in the
  background on the `long` queue.
- The **scheduler enabled** (`bench --site <site> enable-scheduler`) for auto‑upload, schedules and
  retention.
- A cloud account for at least one provider.
- The site must be reachable at a stable URL — the OAuth **redirect URI** must match exactly.

> For OAuth providers on `localhost` / on‑prem, use `http://localhost:8000` (or your real HTTPS domain).
> The redirect URI is shown for you on the provider form — copy it verbatim into the provider console.

---

## 3. Part A — Set up the Cloud Backup app

### 3.1 Install & enable

```bash
bench get-app https://github.com/sanjay-kumar001/cloud_backup
bench --site <your-site> install-app cloud_backup
bench --site <your-site> migrate
bench restart
```

Open the **Cloud Backup** workspace from the desk (a desktop icon is installed on the desk home page).

### 3.2 Create a Provider record

1. Go to **Cloud Backup Provider** → **New** (`/app/cloud-backup-provider/new`).
2. Pick a **Provider Type** (`google_drive`, `dropbox`, `onedrive`, or `amazon_s3`). This also names the
   record and reveals the fields relevant to that provider.
3. Leave **Enabled** ticked.
4. **Save.** (You must save before authorizing.)

### 3.3 Authorize / enter credentials

The credential step depends on the provider — complete the matching section in
[Part B](#4-part-b--providerside-setup) first to obtain your keys, then:

- **Google Drive** — no keys on this form; click **Authorize** and complete the Google consent screen.
- **Dropbox / OneDrive** — paste the **Client ID** and **Client Secret**, **Save**, then click
  **Authorize** and complete the consent screen.
- **Amazon S3** — paste the **Access Key ID** as *Client ID* and the **Secret Access Key** as
  *Client Secret*, set **Bucket** and **Region**, and **Save**.

After authorizing, the **Authentication Status** on the form turns **Authorized** (green). Use the
**Test Connection** button to confirm connectivity.

### 3.4 Select the destination folder / prefix

- **Folder providers (Drive / Dropbox / OneDrive):** click **Select Destination Folder**, browse into the
  target folder (or create one with **New Folder**), and confirm. This stores the destination on the
  provider.
- **Amazon S3:** click **Select Destination Prefix** to pick/create a key prefix inside the bucket
  (e.g. `erp-backups/`). You can also leave it at the bucket root.

A provider is considered **ready** only when it is **Authorized** *and* has a destination selected.

### 3.5 Configure Cloud Backup Settings

Open **Cloud Backup Settings** (`/app/cloud-backup-settings`) — a Single doctype that governs the whole app.

| Field | Purpose |
| --- | --- |
| **Enabled** | Master switch for automatic behaviour. |
| **Default Provider** | The provider uploads normally target. |
| **Fallback Provider** | Used automatically when the default isn't ready — see [§6](#6-fallback-provider). |
| **Automatic Upload After Backup** | Upload as soon as any `bench backup` finishes. |
| **Verify Upload** | Compare remote size/checksum after upload — see [§7](#7-verification). |
| **Include Database / Files / Full** | Which artifacts auto‑upload ships. |
| **Auto‑Delete Remote Backups** | Enables the retention policy — see [§5](#5-retention-policy). |
| **Retention Type / Count / Days** | Keep last *N* backups, or backups newer than *N* days. |
| **History Retention Days** | Purge old, already‑deleted History rows after *N* days. |
| **Enable Notifications** | Notify System Managers on failures and quota warnings. |

Set the **Default Provider**, tick **Automatic Upload After Backup**, choose your backup types, and save.

### 3.6 Add a Schedule (optional)

For time‑based uploads independent of `bench backup`, create a **Cloud Backup Schedule**:

1. **Provider** — which provider this schedule uploads to.
2. **Schedule Type** — `Daily`, `Weekly`, or `Custom`.
3. **Frequency (cron)** — for `Custom`, a standard cron expression (e.g. `0 2 * * *` = 02:00 daily).
4. Tick **Enabled** and save.

The scheduler evaluates due schedules on its regular tick; the backup types uploaded follow the Settings
selection.

---

## 4. Part B — Provider‑side setup

Each provider requires a one‑time app/credential setup in the vendor's console. The **redirect URI** for
OAuth providers is shown on the Cloud Backup Provider form — copy it exactly.

### 4.1 Google Drive

Connecting Google Drive has three parts: a Google Cloud project, Frappe's **Google Settings**, and the
**Cloud Backup Provider** record. The most common failure is a mismatched redirect URI.

**Step 1 — Google Cloud Console**

1. Go to <https://console.cloud.google.com/> and create (or select) a project.
2. **APIs & Services → Library** → enable the **Google Drive API**.
3. **APIs & Services → OAuth consent screen**:
   - User type **External** (or Internal for Workspace).
   - Fill app name, support email, developer email.
   - Add the scope `https://www.googleapis.com/auth/drive.file`.
   - Add your Google account under **Test users** while the app is in *Testing*.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type **Web application**.
   - **Authorized redirect URI**:
     ```
     https://<your-site>/api/method/frappe.integrations.google_oauth.callback
     ```
     (Use `http://localhost:8000/...` for local development.)
   - Save and copy the **Client ID** and **Client Secret**.

**Step 2 — Frappe Google Settings**

1. Open **Google Settings** (`/app/google-settings`).
2. Tick **Enable**, paste the **Client ID** and **Client Secret**.
3. Enable **Google Drive** access. Save.

**Step 3 — Cloud Backup Provider**

1. Create a provider with type `google_drive` and save.
2. Click **Authorize** → complete the Google consent screen → you're returned to the form as
   **Authorized**.
3. **Test Connection**, then **Select Destination Folder**.

### 4.2 Dropbox

**Step 1 — Dropbox App Console**

1. Go to <https://www.dropbox.com/developers/apps> → **Create app**.
2. Choose **Scoped access**, and **App folder** (recommended) or **Full Dropbox** access.
3. Name the app and create it.
4. On the app's **Settings** tab, copy the **App key** and **App secret**.
5. Under **OAuth 2 → Redirect URIs**, add exactly (from the provider form):
   ```
   https://<your-site>/api/method/cloud_backup.services.oauth2_service.callback
   ```
6. On the **Permissions** tab, enable at least:
   `files.content.write`, `files.content.read`, `files.metadata.read`, and (for the storage card)
   `account_info.read`. Submit.

**Step 2 — Cloud Backup Provider**

1. Create a provider with type `dropbox`.
2. Paste the **App key** into **Client ID** and the **App secret** into **Client Secret**. Save.
3. Click **Authorize** → approve → returned as **Authorized**.
4. **Test Connection**, then **Select Destination Folder**.

> Dropbox tokens auto‑refresh: the app key/secret + a stored refresh token let the SDK mint new access
> tokens without re‑authorization.

### 4.3 Microsoft OneDrive

**Step 1 — Azure Portal (App registration)**

1. Go to <https://portal.azure.com/> → **Microsoft Entra ID → App registrations → New registration**.
2. Name the app; supported account types typically **Accounts in any organizational directory and personal
   Microsoft accounts**.
3. **Redirect URI** → platform **Web** → add (from the provider form):
   ```
   https://<your-site>/api/method/cloud_backup.services.oauth2_service.callback
   ```
4. Register, then copy the **Application (client) ID**.
5. **Certificates & secrets → New client secret** → copy the secret **Value** (not the ID).
6. **API permissions → Add a permission → Microsoft Graph → Delegated**: add
   `Files.ReadWrite.All` and `offline_access` (and `User.Read`). Grant admin consent if required.

**Step 2 — Cloud Backup Provider**

1. Create a provider with type `onedrive`.
2. Paste the **Application (client) ID** into **Client ID** and the secret **Value** into **Client
   Secret**. Save.
3. Click **Authorize** → sign in / consent → returned as **Authorized**.
4. **Test Connection**, then **Select Destination Folder**.

### 4.4 Amazon S3

Amazon S3 uses access‑key auth — there is no browser Authorize step.

**Step 1 — Create the bucket**

1. In the AWS console open **S3 → Create bucket**, choose a name and region (note the **Region**, e.g.
   `us-east-1`).

**Step 2 — Create an IAM user + keys**

1. **IAM → Users → Create user** (programmatic access).
2. Attach a **least‑privilege policy** scoped to your bucket, for example:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"],
         "Resource": [
           "arn:aws:s3:::your-bucket",
           "arn:aws:s3:::your-bucket/*"
         ]
       }
     ]
   }
   ```
3. Create an **access key** and copy the **Access Key ID** and **Secret Access Key**.

**Step 3 — Cloud Backup Provider**

1. Create a provider with type `amazon_s3`.
2. Enter the **Access Key ID** in **Client ID** and the **Secret Access Key** in **Client Secret**.
3. Set **Bucket** and **Region**. Save.
4. **Test Connection** (head‑bucket), then **Select Destination Prefix** (or leave at bucket root).

---

## 5. Retention policy

Retention deletes **only** files that Cloud Backup itself uploaded (tracked in History) — it never touches
anything else in your cloud storage.

**Enable it** in Cloud Backup Settings with **Auto‑Delete Remote Backups**, then choose:

| Retention Type | Keeps | Deletes |
| --- | --- | --- |
| **Count** | The newest **Backups to Keep** (`retention_count`) per provider | Everything older than the Nth newest |
| **Age** | Backups newer than **Retention Days** (`retention_days`) | Anything older than the cutoff |

**When it runs:**

- **After every successful upload** — a cleanup scoped to *that* provider (only its set could have
  changed).
- **Daily** — a full pass across every managed provider, plus **History housekeeping**.

**History housekeeping** — when **History Retention Days** > 0, History rows whose remote file is already
deleted and older than the window are permanently removed, keeping the table tidy.

**Guarantees:**

- **Idempotent** — safe to run repeatedly; already‑deleted files are skipped.
- **Per‑provider** — each provider is pruned against its own newest‑first list.
- **Recorded** — every run writes to the Cloud Backup Log and updates *Last Cleanup* on Settings.

Run it on demand any time with `bench cloud-backup cleanup`.

---

## 6. Fallback provider

The **Fallback Provider** is your safety net. When an upload is triggered, Cloud Backup resolves the target
like this:

1. If the **Default Provider** is **ready** (Authorized + has a destination) → use it.
2. Else if the **Fallback Provider** is ready → use it.
3. Else → the upload is skipped (and logged).

This means a broken/expired default (e.g. revoked OAuth) automatically diverts new backups to the fallback
instead of failing silently. Set the fallback to a *different* provider for real redundancy — e.g. default
Google Drive, fallback Amazon S3.

> Scheduled uploads always target their own schedule's provider; the default/fallback resolution applies to
> auto‑upload and the CLI.

---

## 7. Verification

Tick **Verify Upload** in Settings to have each upload validated after it lands:

- The remote file's **size** is compared to the local artifact.
- The remote **checksum** (where the provider exposes one) is compared to what was sent.
- The result is stored on the History row as **Verification Status** (`Verified` / `Failed`).

Verification failures do not delete the remote file; they flag the row so you can investigate.

---

## 8. Notifications & quota warnings

With **Enable Notifications** on:

- **Upload failures** notify System Managers with the error message.
- **Quota warnings** — a daily check notifies when an authorized provider's storage crosses the warning
  threshold (90% by default). Object stores like S3 have no account quota and are not warned.

The dashboard surfaces the same health at a glance (health pill, storage cards, failed‑upload count).

---

## 9. Command line (CLI)

All commands run in a site context and exit non‑zero on failure (CI‑friendly):

```bash
bench cloud-backup                     # backup + upload (database only)
bench cloud-backup --with-files        # backup + upload including files
bench cloud-backup test                # test connectivity to the resolved provider
bench cloud-backup list --limit 10     # recent upload history
bench cloud-backup cleanup             # run retention now
bench cloud-backup status              # provider, last-upload status, health
bench cloud-backup restore <history>   # download a cloud backup for bench restore
```

---

## 10. Restore

Cloud Backup can pull a stored backup back down for a native restore:

```bash
# 1. Find the History row id (e.g. from `bench cloud-backup list` or the History list view)
bench cloud-backup restore CBH-2026-00042

# 2. It downloads into private/backups and prints the exact restore command, e.g.:
bench --site <your-site> restore /path/to/private/backups/<file>.sql.gz
```

You can also trigger a download from the **Cloud Backup History** record in the desk.

---

## 11. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| **Authorization failed** after consent | Redirect URI mismatch — copy the URI from the provider form *exactly* into the provider console (scheme, host, port, path). |
| Status stays **Not Configured** after a successful consent | The OAuth callback is a GET; ensure you're on the latest build (the callback commits the tokens explicitly). Retry Authorize. |
| **No files backup getting uploaded** | Tick **Include Files Backup** in Settings; the latest on‑disk backup may be database‑only — the app regenerates missing artifacts on demand. |
| Upload stuck in **Queued** | No worker running — start `bench worker` / `bench start`; uploads run on the `long` queue. |
| **Test Connection** fails for S3 | Check bucket name, region, and that the IAM policy allows `s3:ListBucket` / `PutObject` on the bucket ARN. |
| Retention deletes nothing | **Auto‑Delete Remote Backups** is off, or fewer backups exist than **Backups to Keep**. |
| Nothing auto‑uploads | **Enabled** + **Automatic Upload After Backup** must both be on, and the default/fallback provider must be *ready*. |
| Dashboard labels look stale | `bench --site <site> clear-cache` and hard‑reload (Ctrl/Cmd+Shift+R). |

Dedicated logs live in **Cloud Backup Log** (`/app/cloud-backup-log`); every upload attempt is in
**Cloud Backup History**.
