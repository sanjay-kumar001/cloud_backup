# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Google Drive OAuth wiring constants and domain registration."""

# Own GoogleOAuth "domain" key so we never clobber core's shared "drive" scope.
DRIVE_DOMAIN = "cloud_backup_drive"
# Non-restricted scope: access is limited to files/folders this app creates,
# so it avoids Google's restricted-scope (full Drive) CASA verification.
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_CALLBACK_METHOD = "cloud_backup.services.oauth_service.authorize_access"
DRIVE_SERVICE_VERSION = ("drive", "v3")
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


def register_domain() -> None:
	"""Register this app's drive domain (scope/service/callback) on GoogleOAuth."""
	from frappe.integrations import google_oauth

	google_oauth._SCOPES[DRIVE_DOMAIN] = DRIVE_SCOPE
	google_oauth._SERVICES[DRIVE_DOMAIN] = DRIVE_SERVICE_VERSION
	google_oauth._DOMAIN_CALLBACK_METHODS[DRIVE_DOMAIN] = DRIVE_CALLBACK_METHOD
