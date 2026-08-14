# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Generic OAuth2 authorize/callback/refresh for non-Google providers."""

from __future__ import annotations

from urllib.parse import quote, urlencode

import frappe
import requests
from frappe.utils import add_to_date, get_url, now_datetime

from cloud_backup.utils.constants import HTTP_TIMEOUT
from cloud_backup.utils.exceptions import AuthenticationError

CALLBACK_METHOD = "cloud_backup.services.oauth2_service.callback"
_STATE_PREFIX = "cb_oauth2_state:"
_STATE_TTL = 600
_DEFAULT_TOKEN_TTL = 3600


def get_config(provider_type: str) -> dict:
	"""Return the OAuth2 endpoint config for a provider_type; raise if unsupported."""
	if provider_type == "onedrive":
		from cloud_backup.providers.onedrive import OAUTH2_CONFIG
	elif provider_type == "dropbox":
		from cloud_backup.providers.dropbox import OAUTH2_CONFIG
	else:
		raise AuthenticationError(f"No OAuth2 flow registered for '{provider_type}'")
	return OAUTH2_CONFIG


def redirect_uri() -> str:
	"""Runtime callback URL (scheme/host from the live site; never hardcoded)."""
	return get_url(f"/api/method/{CALLBACK_METHOD}")


def get_authorization_url(provider: str) -> dict[str, str]:
	"""Build the provider consent URL and stash a CSRF state token."""
	doc = frappe.get_doc("Cloud Backup Provider", provider)
	doc.check_permission("write")
	config = get_config(doc.provider_type)
	client_id = doc.get_password("client_id", raise_exception=False)
	if not client_id:
		raise AuthenticationError("Set the Client ID before authorizing")

	state = frappe.generate_hash(length=48)
	frappe.cache().set_value(_STATE_PREFIX + state, provider, expires_in_sec=_STATE_TTL)
	params = {
		"client_id": client_id,
		"response_type": "code",
		"redirect_uri": redirect_uri(),
		"scope": config["scope"],
		"state": state,
		**config.get("extra_authorize_params", {}),
	}
	return {"url": f"{config['authorize_url']}?{urlencode(params)}"}


@frappe.whitelist(allow_guest=True)
def callback(code: str | None = None, state: str | None = None, **kwargs) -> None:
	"""OAuth2 redirect target: exchange the code and store tokens, then redirect."""
	provider = frappe.cache().get_value(_STATE_PREFIX + (state or "")) if state else None
	if not provider:
		frappe.throw(frappe._("Invalid or expired OAuth state"), frappe.PermissionError)
	frappe.cache().delete_value(_STATE_PREFIX + state)
	doc = frappe.get_doc("Cloud Backup Provider", provider)
	form_route = f"/app/cloud-backup-provider/{provider}"
	if kwargs.get("error") or not code:
		reason = kwargs.get("error_description") or kwargs.get("error") or "No authorization code returned"
		_fail(doc, form_route, reason)
		return
	try:
		tokens = _exchange_code(doc, code)
		_store_tokens(doc, tokens)
	except Exception as exc:
		_fail(doc, form_route, getattr(exc, "message", None) or str(exc))
		return
	_redirect(f"{form_route}?cb_authorized=1")


def _fail(doc, form_route: str, reason: str) -> None:
	"""Record the auth failure (Cloud Backup Log + Error Log) and surface it."""
	from cloud_backup.services import log_service

	doc.db_set("authentication_status", "Failed")
	log_service.write_log(
		"oauth_failed", f"{doc.name}: {reason}", level="ERROR", source="oauth2_service"
	)
	frappe.log_error(title="Cloud Backup OAuth2", message=f"{doc.name}: {reason}")
	_redirect(f"{form_route}?cb_authorized=0&cb_reason={quote(reason[:180])}")


def refresh_token(doc) -> None:
	"""Refresh an expired OAuth2 access token; mark Expired on failure."""
	refresh = doc.get_password("refresh_token", raise_exception=False)
	if not refresh:
		doc.db_set("authentication_status", "Expired", commit=False)
		raise AuthenticationError("No refresh token stored; re-authorization required")
	config = get_config(doc.provider_type)
	payload = {
		"grant_type": "refresh_token",
		"refresh_token": refresh,
		"client_id": doc.get_password("client_id", raise_exception=False),
		"client_secret": doc.get_password("client_secret", raise_exception=False),
	}
	if config.get("scope"):
		payload["scope"] = config["scope"]
	try:
		tokens = _post_token(config["token_url"], payload)
	except Exception as exc:
		doc.db_set("authentication_status", "Expired", commit=False)
		raise AuthenticationError("OAuth2 token refresh failed") from exc
	_store_tokens(doc, tokens, keep_refresh=refresh)


def _exchange_code(doc, code: str) -> dict:
	"""Exchange an authorization code for access/refresh tokens."""
	config = get_config(doc.provider_type)
	payload = {
		"grant_type": "authorization_code",
		"code": code,
		"redirect_uri": redirect_uri(),
		"client_id": doc.get_password("client_id", raise_exception=False),
		"client_secret": doc.get_password("client_secret", raise_exception=False),
	}
	if config.get("scope"):
		payload["scope"] = config["scope"]
	return _post_token(config["token_url"], payload)


def _post_token(token_url: str, payload: dict) -> dict:
	"""POST the token endpoint (form-encoded) and return the JSON token set."""
	response = requests.post(token_url, data=payload, timeout=HTTP_TIMEOUT)
	if not response.ok:
		raise AuthenticationError(f"Token endpoint returned {response.status_code}: {_error_text(response)}")
	tokens = response.json()
	if not tokens.get("access_token"):
		raise AuthenticationError("Token endpoint returned no access token")
	return tokens


def _error_text(response) -> str:
	"""Extract a short provider error message from a token-endpoint failure."""
	try:
		data = response.json()
	except ValueError:
		return (response.text or "")[:180]
	return str(data.get("error_description") or data.get("error_summary") or data.get("error") or data)[:180]


def _store_tokens(doc, tokens: dict, keep_refresh: str | None = None) -> None:
	"""Persist access/refresh tokens, expiry and Authorized status."""
	doc.access_token = tokens["access_token"]
	doc.refresh_token = tokens.get("refresh_token") or keep_refresh
	doc.token_expiry = add_to_date(
		now_datetime(), seconds=int(tokens.get("expires_in") or _DEFAULT_TOKEN_TTL)
	)
	doc.authentication_status = "Authorized"
	doc.save(ignore_permissions=True)


def _redirect(location: str) -> None:
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
