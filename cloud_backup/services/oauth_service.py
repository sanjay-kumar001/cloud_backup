# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Google OAuth flow: authorize URL, callback, token refresh."""

from __future__ import annotations

import frappe
from frappe.integrations import google_oauth as _google_oauth
from frappe.integrations.google_oauth import GoogleAuthenticationError, GoogleOAuth
from frappe.utils import add_to_date, now_datetime

from cloud_backup.providers.google_drive import (
	DRIVE_CALLBACK_METHOD,
	DRIVE_DOMAIN,
	DRIVE_SERVICE_VERSION,
)
from cloud_backup.utils.exceptions import AuthenticationError

PROVIDER_DOCTYPE = "Cloud Backup Provider"
_DEFAULT_TOKEN_TTL = 3600


def register_drive_domain(*args, **kwargs) -> None:
	"""Map the drive domain to this app's callback for the shared handler."""
	_google_oauth._DOMAIN_CALLBACK_METHODS[DRIVE_DOMAIN] = DRIVE_CALLBACK_METHOD
	_google_oauth._SERVICES[DRIVE_DOMAIN] = DRIVE_SERVICE_VERSION


def get_drive_oauth() -> GoogleOAuth:
	"""Return a GoogleOAuth('drive') validated against Google Settings."""
	register_drive_domain()
	return GoogleOAuth(
		DRIVE_DOMAIN,
		config={
			"domain_callback_url": DRIVE_CALLBACK_METHOD,
			"service_version": DRIVE_SERVICE_VERSION,
		},
	)


def get_authorization_url(provider: str) -> dict[str, str]:
	"""Return the Google consent URL for the given provider record."""
	frappe.has_permission(PROVIDER_DOCTYPE, "write", doc=provider, throw=True)
	oauth = get_drive_oauth()
	state = {
		"provider": provider,
		"redirect": f"/app/cloud-backup-provider/{provider}",
		"success_query_param": "cb_authorized=1",
		"failure_query_param": "cb_authorized=0",
	}
	return oauth.get_authentication_url(state)


def authorize_access(provider: str, code: str | None = None, **kwargs) -> None:
	"""Shared-callback target: exchange the code and store Drive tokens."""
	doc = frappe.get_doc(PROVIDER_DOCTYPE, provider)
	doc.check_permission("write")
	tokens = get_drive_oauth().authorize(code) if code else {}
	if not tokens.get("access_token"):
		doc.db_set("authentication_status", "Failed", commit=False)
		frappe.msgprint(frappe._("Google Drive authorization failed"), indicator="red")
		return
	_store_tokens(doc, tokens)
	frappe.msgprint(frappe._("Google Drive authorized"), indicator="green")


def refresh_token(doc) -> None:
	"""Refresh an expired Drive access token; mark Expired on failure."""
	refresh = doc.get_password("refresh_token", raise_exception=False)
	if not refresh:
		doc.db_set("authentication_status", "Expired", commit=False)
		raise AuthenticationError("No refresh token stored; re-authorization required")
	try:
		tokens = get_drive_oauth().refresh_access_token(refresh)
	except GoogleAuthenticationError as exc:
		doc.db_set("authentication_status", "Expired", commit=False)
		raise AuthenticationError("Google token refresh failed") from exc
	_store_tokens(doc, tokens, keep_refresh=refresh)


def _store_tokens(doc, tokens: dict, keep_refresh: str | None = None) -> None:
	"""Persist access/refresh tokens, expiry and Authorized status."""
	doc.access_token = tokens["access_token"]
	doc.refresh_token = tokens.get("refresh_token") or keep_refresh
	doc.token_expiry = add_to_date(
		now_datetime(), seconds=int(tokens.get("expires_in") or _DEFAULT_TOKEN_TTL)
	)
	doc.authentication_status = "Authorized"
	doc.save(ignore_permissions=True)
