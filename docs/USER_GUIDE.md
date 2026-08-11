# Cloud Backup — User Guide

Automated cloud backup upload for Frappe / ERPNext. This guide covers **Google Drive** setup end to end,
including the localhost/on-prem quirks and the Google consent-screen steps.

---

## 1. Google Drive — One-Time Setup

Connecting Google Drive has three parts: a Google Cloud project, Frappe's **Google Settings**, and a
per-record **Cloud Backup Provider**. The single most common failure is the **OAuth redirect URI**, so read
§1.3 carefully.

### 1.1 Google Cloud Console

1. Create (or reuse) a project at <https://console.cloud.google.com>.
2. **APIs & Services → Library →** enable **Google Drive API**.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID → Application type: Web
   application**.
4. Note the **Client ID** and **Client Secret**.
5. Add the **Authorized redirect URI** — see §1.3 for the exact value (this is where most setups fail).

### 1.2 Frappe Google Settings

In Desk open **Google Settings** and set:

- **Enable** → on
- **Client ID** / **Client Secret** → from §1.1
- **Enable Google Drive Picker** → on

> ⚠️ **The Client Secret must actually be entered and saved.** It is a Password field, so after saving it
> shows blank — that is normal, but if it was never populated, `get_password("client_secret")` returns empty
> and every authorization fails with **"client_secret is missing."** (Google Cloud no longer lets you view an
> existing secret; if you don't have the value, create a new one under **Credentials → your OAuth client →
> Add secret** and paste it.) Verify with:
> ```bash
> bench --site <your-site> console
> >>> bool(frappe.get_single("Google Settings").get_password("client_secret", raise_exception=False))
> True
> ```

### 1.3 The redirect URI (critical)

The redirect URI Cloud Backup uses is always:

```
<site-url>/api/method/frappe.integrations.google_oauth.callback
```

where `<site-url>` is **whatever Frappe's `get_url()` returns** — which is driven by the site's
`host_name`, **not** by the address in your browser.

Google enforces a "secure OAuth" policy on this URI. It **rejects**:

- plain **`http://`** on any host other than loopback, and
- **reserved/invalid TLDs** such as `.local`, `.test`, `.internal`.

Google **accepts**:

- **`http://localhost[:port]`** or **`http://127.0.0.1[:port]`** (loopback exemption — http allowed), or
- a real **`https://`** public domain.

> A site served as `http://test.local` (or `https://test.local`) will fail with
> **`Error 400: invalid_request` — "doesn't comply with Google's OAuth 2.0 policy"**, because `.local` is a
> reserved TLD. Use loopback for local dev (§1.4) or a real HTTPS domain for production (§1.7).

### 1.4 Localhost / on-prem development site configuration

To authorize on a developer machine, serve the site over **loopback** so Google accepts the redirect URI.

1. **Find the web port** (`webserver_port` in `sites/common_site_config.json`; Frappe's default is `8000`).
2. **Make loopback resolve to your site** — set it as the default site so `localhost` maps to it:
   ```bash
   bench use <your-site>            # or: echo "<your-site>" > sites/currentsite.txt
   ```
3. **Pin `host_name` to loopback** so `get_url()` emits the loopback redirect URI:
   ```bash
   bench --site <your-site> set-config host_name "http://localhost:8000"   # match your port
   bench --site <your-site> clear-cache
   ```
4. **Register the matching redirect URI** in the Google Cloud OAuth client (§1.1 step 5):
   ```
   http://localhost:8000/api/method/frappe.integrations.google_oauth.callback
   ```
5. Always open Desk via **`http://localhost:8000`** while authorizing (not the `.local` host).

Verify the URI Frappe will send:

```bash
bench --site <your-site> console
>>> from frappe.utils import get_url
>>> from frappe.integrations.google_oauth import CALLBACK_METHOD
>>> get_url() + CALLBACK_METHOD
'http://localhost:8000/api/method/frappe.integrations.google_oauth.callback'
```

This must match the registered URI **exactly** (scheme, host, port, path).

**Site name, `/etc/hosts`, and nginx**

- **Site name vs `host_name` — two different things:**
  - The **site directory name** (`sites/<name>/`) is the `Host` your site *answers to*. Frappe matches the
    request's `Host` header (port stripped) to a site folder.
  - **`host_name`** (in `site_config.json`) controls the URLs Frappe *generates* via `get_url()` — this is
    what forms the OAuth redirect URI.

  You do **not** need to rename your site to `localhost`. Keep the real site name and make it the **default
  site** (`currentsite.txt`, §1.4 step 2) so a request to `http://localhost` — which matches no site folder —
  falls back to it. Setting `host_name = http://localhost:8000` only changes the *generated* URLs.
- **`/etc/hosts`:** `localhost` already resolves to `127.0.0.1` everywhere, so **no hosts entry is required**
  for the loopback flow. A line like `127.0.0.1  test.local` only exists to let you browse a *custom*
  hostname — and that custom `.local` host is exactly what Google rejects (§1.3), so it is not used for OAuth.
- **nginx is not needed for local OAuth.** Hit the Frappe dev server directly on the loopback port:
  ```bash
  bench serve --port 8000      # or: bench start  (serves on webserver_port)
  ss -ltn | grep 8000          # confirm it is listening
  ```
  then browse `http://localhost:8000`.
- **If nginx is in front** (e.g. TLS on `:443` for a custom host): either bypass it for OAuth using the
  loopback dev port above, or go the production route (§1.7) with a real HTTPS domain. If you keep nginx it
  must forward the headers Frappe relies on —
  ```nginx
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto $scheme;   # so Frappe emits https:// URLs
  ```
  regenerate the managed config with `bench setup nginx` and reload. Do **not** point OAuth at an nginx vhost
  served as `http://<name>.local` — same policy block as §1.3.

### 1.5 OAuth consent screen & test users

While the Google app is unverified it runs in **Testing** mode and only **approved testers** may authorize.

1. **APIs & Services → OAuth consent screen** (newer console: the **Audience** tab).
2. Under **Test users → + Add users**, add the exact Google account you will authorize with
   (e.g. `you@gmail.com`). **Save.**
3. Confirm the scope `https://www.googleapis.com/auth/drive.file` is present (see §1.8 on scope choice).

> Without this you get **`Error 403: access_denied` — "<App> has not completed the Google verification
> process … can only be accessed by developer-approved testers."** Add the account as a test user and retry.

### 1.6 Authorize in Cloud Backup

1. Open **Cloud Backup Provider**, create a record: set **Provider Name** and **Provider Type =
   google_drive**, then **Save**.
2. Click **Authorize** → complete Google consent with a test-user account → you return to the form with
   status **Authorized** (green).
3. Click **Test Connection** — expect *"Connected as you@gmail.com"*.
4. Click **Select Destination Folder** — **create** the backup folder here (e.g. "ERPNext Backups") and
   select it; the selection is saved on the provider as the upload target.

> **Folder browser & the `drive.file` scope:** the app uses the narrow `drive.file` scope (§1.8), which grants
> access **only to files and folders this app creates** (or that you pick via the Google Picker). So the
> folder browser lists app-created folders, **not** your entire Drive. Create the destination folder with the
> **New Folder** button and the app will manage it. This is the expected, safer behaviour for a backup app.

### 1.7 Production configuration

For a real deployment, serve the site over HTTPS on a public domain and use that everywhere:

- `host_name = https://backups.example.com`
- Registered redirect URI = `https://backups.example.com/api/method/frappe.integrations.google_oauth.callback`
- Revert any localhost `host_name`/`currentsite.txt` changes made for dev.

### 1.8 OAuth scope choice (`drive.file`, not full Drive)

Cloud Backup requests **`https://www.googleapis.com/auth/drive.file`** — a **non-restricted** scope — instead
of the full `drive` scope. This is deliberate:

- **Full `drive`** is a **restricted** scope: to publish publicly without warnings, Google requires an annual
  paid **CASA** security assessment.
- **`drive.file`** avoids that path. The app can only see/manage what it creates, which is exactly what a
  backup app needs, and it sidesteps the restricted-scope verification burden.

The app registers this on its **own** OAuth "domain" (`cloud_backup_drive`), so it never changes the scope of
Frappe's shared `drive` integration. Trade-off: the folder browser only shows app-created folders (see §1.6).

---

## 2. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Error 400: invalid_request` — "doesn't comply with Google's OAuth 2.0 policy" | Redirect URI is http on a non-loopback host, or uses a reserved TLD (`.local`/`.test`) | Use `http://localhost:<port>` (§1.4) or a real HTTPS domain (§1.7) |
| `Error 400: redirect_uri_mismatch` | The URI Frappe sent isn't registered in the OAuth client | Register the exact `get_url()+callback` value (§1.4) |
| `Error 403: access_denied` — "has not completed the Google verification process" | App in Testing mode; account isn't a test user | Add the account under **Test users** (§1.5) |
| Provider stuck at **Failed** right after authorizing (Error Log: *"client_secret is missing"*) | Google Settings Client Secret is empty | Re-enter the Client Secret in **Google Settings** and Save (§1.2), then Authorize again |
| Green "authorized" toast but provider shows **Failed** | (Older builds) toast trusted the callback URL param, not the real result | Fixed — the toast now reflects `authentication_status`. Check the Error Log for the real cause |
| Authorize button missing on the form | Record unsaved, or `provider_type` not set | Save the record with `provider_type = google_drive`; hard-refresh |
| Status flips to **Expired** after ~7 days | Testing-mode refresh tokens expire in 7 days | Re-Authorize, or publish the app (§3) |

---

## 3. Publishing, verification & cost

**Is publishing paid?** No — clicking **OAuth consent screen → Publish app** (moving from Testing to
Production) is **free**, and so is Google's verification review.

Because this app uses the **non-restricted `drive.file`** scope (§1.8), it **does not** trigger the paid
restricted-scope (full-Drive) verification/CASA path. Remaining nuances:

- **Testing mode (free):** only test users; refresh tokens **expire after 7 days** (you re-authorize weekly).
- **Published (free):** removes the 7-day refresh-token expiry. With `drive.file` there is **no CASA
  requirement**. Depending on Google's current policy you may still see a one-time "unverified app" notice
  for a sensitive scope — click **Advanced → Go to <App> (unsafe) → Continue**; harmless for self-hosting.
- **Internal user type (free, no verification, no warning):** only if the Google account belongs to a
  **Google Workspace organization**. Not available for a plain `@gmail.com`.

**Practical guidance (personal `@gmail.com`, self-hosted):** **Publish** the app (removes the 7-day expiry)
and keep the `drive.file` scope — no paid assessment is required. The occasional unverified notice is
click-through only.

---

## 4. Token Expiry & Re-Authorization

- Cloud Backup refreshes the Drive access token automatically before each use.
- If the **refresh token** is revoked or expires (e.g. the 7-day Testing limit), the provider status becomes
  **Expired** and uploads stop. Open the provider and click **Authorize** again to restore access.
