# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""OAuth2 for non-Google providers: Dropbox (SDK flow) and OneDrive (MSAL)."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote

import frappe
from frappe.utils import add_to_date, get_url, now_datetime

from cloud_backup.utils.exceptions import AuthenticationError

CALLBACK_METHOD = "cloud_backup.services.oauth2_service.callback"
_STATE_PREFIX = "cb_oauth2_state:"
_DBX_CSRF_KEY = "cb-dropbox-csrf-token"
_STATE_TTL = 3600
_DEFAULT_TOKEN_TTL = 3600

# OneDrive (Microsoft Graph, delegated) — offline_access is added by MSAL.
_MS_AUTHORITY = "https://login.microsoftonline.com/common"
_MS_SCOPES = ["Files.ReadWrite", "User.Read"]


def redirect_uri() -> str:
	"""Runtime callback URL (scheme/host from the live site; never hardcoded)."""
	return get_url(f"/api/method/{CALLBACK_METHOD}")


def _encode_state(provider: str, nonce: str) -> str:
	"""URL-safe token carrying the provider (recoverable if the cache expires)."""
	raw = json.dumps({"p": provider, "n": nonce}).encode()
	return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_state(state: str) -> tuple[str | None, str | None]:
	"""Return (provider, nonce) from an encoded state, or (None, None)."""
	try:
		padded = state + "=" * (-len(state) % 4)
		data = json.loads(base64.urlsafe_b64decode(padded))
		return data.get("p"), data.get("n")
	except Exception:
		return None, None


def get_authorization_url(provider: str) -> dict[str, str]:
	"""Build the provider consent URL (Dropbox SDK flow or OneDrive MSAL)."""
	doc = frappe.get_doc("Cloud Backup Provider", provider)
	doc.check_permission("write")
	if not doc.get_password("client_id", raise_exception=False):
		raise AuthenticationError("Set the Client ID before authorizing")
	if doc.provider_type == "dropbox":
		return {"url": _dropbox_flow(doc).start(url_state=doc.name)}
	if doc.provider_type == "onedrive":
		return {"url": _onedrive_authorize_url(doc)}
	raise AuthenticationError(f"No OAuth2 flow registered for '{doc.provider_type}'")


@frappe.whitelist(allow_guest=True)
def callback(code: str | None = None, state: str | None = None, **kwargs) -> None:
	"""OAuth2 redirect target: route to the OneDrive (MSAL) or Dropbox (SDK) flow."""
	_log(
		"oauth_callback_hit",
		f"state_len={len(state or '')} pipe={'|' in (state or '')} code={bool(code)} err={kwargs.get('error')}",
	)
	provider, nonce = _decode_state(state or "")
	if provider:
		_onedrive_callback(provider, nonce, code, kwargs)
	else:
		_dropbox_callback(state or "", code, kwargs)


# --- OneDrive (MSAL) --------------------------------------------------------


def _msal_app(doc):
	"""Return an MSAL confidential client bound to this provider's app registration."""
	import msal

	return msal.ConfidentialClientApplication(
		client_id=doc.get_password("client_id", raise_exception=False),
		client_credential=doc.get_password("client_secret", raise_exception=False),
		authority=_MS_AUTHORITY,
	)


def _onedrive_authorize_url(doc) -> str:
	"""Microsoft consent URL via MSAL, with a CSRF nonce stashed in Redis."""
	nonce = frappe.generate_hash(length=48)
	frappe.cache().set_value(_STATE_PREFIX + nonce, doc.name, expires_in_sec=_STATE_TTL)
	return _msal_app(doc).get_authorization_request_url(
		_MS_SCOPES, state=_encode_state(doc.name, nonce), redirect_uri=redirect_uri()
	)


def _onedrive_callback(provider: str, nonce: str | None, code: str | None, kwargs: dict) -> None:
	"""Complete OneDrive authorization via MSAL; resilient to CSRF-cache expiry."""
	if not frappe.db.exists("Cloud Backup Provider", provider):
		frappe.throw(frappe._("Invalid OAuth state"), frappe.PermissionError)
	cached = frappe.cache().get_value(_STATE_PREFIX + (nonce or ""))
	frappe.cache().delete_value(_STATE_PREFIX + (nonce or ""))
	doc = frappe.get_doc("Cloud Backup Provider", provider)
	form_route = f"/app/cloud-backup-provider/{provider}"
	if not cached:
		_log("oauth_state_cache_miss", f"{provider}: CSRF nonce expired; proceeding", level="WARNING")
	if kwargs.get("error") or not code:
		reason = kwargs.get("error_description") or kwargs.get("error") or "No authorization code returned"
		_fail(doc, form_route, reason)
		return
	result = _msal_app(doc).acquire_token_by_authorization_code(
		code, scopes=_MS_SCOPES, redirect_uri=redirect_uri()
	)
	if "access_token" not in result:
		_fail(doc, form_route, _msal_reason(result))
		return
	_store_msal_result(doc, result)
	_redirect(f"{form_route}?cb_authorized=1")


def refresh_onedrive(doc) -> None:
	"""Refresh an expired OneDrive access token via MSAL; mark Expired on failure."""
	refresh = doc.get_password("refresh_token", raise_exception=False)
	if not refresh:
		doc.db_set("authentication_status", "Expired", commit=False)
		raise AuthenticationError("No refresh token stored; re-authorization required")
	result = _msal_app(doc).acquire_token_by_refresh_token(refresh, scopes=_MS_SCOPES)
	if "access_token" not in result:
		doc.db_set("authentication_status", "Expired", commit=False)
		raise AuthenticationError(_msal_reason(result))
	_store_msal_result(doc, result, keep_refresh=refresh)


def _store_msal_result(doc, result: dict, keep_refresh: str | None = None) -> None:
	"""Persist tokens from an MSAL result and mark Authorized."""
	doc.access_token = result["access_token"]
	doc.refresh_token = result.get("refresh_token") or keep_refresh
	doc.token_expiry = add_to_date(
		now_datetime(), seconds=int(result.get("expires_in") or _DEFAULT_TOKEN_TTL)
	)
	doc.authentication_status = "Authorized"
	doc.save(ignore_permissions=True)
	# OAuth callbacks are GET requests, which Frappe does not auto-commit.
	frappe.db.commit()


def _msal_reason(result: dict) -> str:
	"""Human-readable reason from an MSAL error result."""
	return str(result.get("error_description") or result.get("error") or "Token exchange failed")[:180]


# --- Dropbox (official SDK flow) -------------------------------------------


def _dropbox_callback(state: str, code: str | None, kwargs: dict) -> None:
	"""Complete Dropbox authorization via the SDK's DropboxOAuth2Flow.finish()."""
	provider = state.split("|", 1)[1] if "|" in state else ""
	if not provider or not frappe.db.exists("Cloud Backup Provider", provider):
		frappe.throw(frappe._("Invalid OAuth state"), frappe.PermissionError)
	doc = frappe.get_doc("Cloud Backup Provider", provider)
	form_route = f"/app/cloud-backup-provider/{provider}"
	query = {"state": state, "code": code, **{k: v for k, v in kwargs.items() if v is not None}}
	try:
		result = _dropbox_flow(doc).finish(query)
	except Exception as exc:
		_fail(doc, form_route, _dropbox_reason(exc))
		return
	_store_dropbox_result(doc, result)
	_redirect(f"{form_route}?cb_authorized=1")


class _RedisSession:
	"""Mutable mapping backing DropboxOAuth2Flow's CSRF store in Redis (per provider)."""

	def __init__(self, provider: str) -> None:
		self.provider = provider

	def _key(self, key: str) -> str:
		return f"cb_dbx_oauth:{self.provider}:{key}"

	def __setitem__(self, key: str, value) -> None:
		frappe.cache().set_value(self._key(key), value, expires_in_sec=_STATE_TTL)

	def __getitem__(self, key: str):
		value = frappe.cache().get_value(self._key(key))
		if value is None:
			raise KeyError(key)
		return value

	def __delitem__(self, key: str) -> None:
		frappe.cache().delete_value(self._key(key))

	def __contains__(self, key: str) -> bool:
		return frappe.cache().get_value(self._key(key)) is not None


def _dropbox_flow(doc):
	"""Return a DropboxOAuth2Flow bound to this provider's app key/secret."""
	from dropbox import DropboxOAuth2Flow

	return DropboxOAuth2Flow(
		consumer_key=doc.get_password("client_id", raise_exception=False),
		redirect_uri=redirect_uri(),
		session=_RedisSession(doc.name),
		csrf_token_session_key=_DBX_CSRF_KEY,
		consumer_secret=doc.get_password("client_secret", raise_exception=False),
		token_access_type="offline",
	)


def _store_dropbox_result(doc, result) -> None:
	"""Persist tokens from a DropboxOAuth2Flow result and mark Authorized."""
	doc.access_token = result.access_token
	if getattr(result, "refresh_token", None):
		doc.refresh_token = result.refresh_token
	expiry = getattr(result, "expires_at", None)
	doc.token_expiry = (
		expiry.replace(tzinfo=None) if expiry else add_to_date(now_datetime(), seconds=_DEFAULT_TOKEN_TTL)
	)
	doc.authentication_status = "Authorized"
	doc.save(ignore_permissions=True)
	# OAuth callbacks are GET requests, which Frappe does not auto-commit.
	frappe.db.commit()


def _dropbox_reason(exc: Exception) -> str:
	"""Human-readable reason for a DropboxOAuth2Flow failure."""
	from dropbox.oauth import BadStateException, CsrfException, NotApprovedException

	if isinstance(exc, BadStateException):
		return "Authorization session expired — click Authorize again"
	if isinstance(exc, CsrfException):
		return "State mismatch (CSRF) — click Authorize again"
	if isinstance(exc, NotApprovedException):
		return "Dropbox authorization was not approved"
	return getattr(exc, "message", None) or str(exc)


# --- shared -----------------------------------------------------------------


def _fail(doc, form_route: str, reason: str) -> None:
	"""Record the auth failure (Cloud Backup Log + Error Log) and surface it."""
	doc.db_set("authentication_status", "Failed")
	frappe.db.commit()  # GET request: commit so the Failed status persists
	_log("oauth_failed", f"{doc.name}: {reason}", level="ERROR")
	frappe.log_error(title="Cloud Backup OAuth2", message=f"{doc.name}: {reason}")
	_redirect(f"{form_route}?cb_authorized=0&cb_reason={quote(reason[:180])}")


def _log(event: str, message: str, level: str = "INFO") -> None:
	from cloud_backup.services import log_service

	log_service.write_log(event, message, level=level, source="oauth2_service")


def _redirect(location: str) -> None:
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
