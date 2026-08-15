# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Resolve an authenticated provider instance from a provider record."""

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.providers.registry import get_provider_class
from cloud_backup.services import oauth2_service, oauth_service
from cloud_backup.utils.constants import OBJECT_PROVIDERS


def get_provider(provider: str | Document) -> CloudBackupProvider:
	"""Return an authenticated provider instance, refreshing tokens if stale."""
	doc = provider if isinstance(provider, Document) else frappe.get_doc("Cloud Backup Provider", provider)
	_ensure_valid_token(doc)
	instance = get_provider_class(doc.provider_type)(_build_config(doc))
	instance.authenticate()
	return instance


def _ensure_valid_token(doc: Document) -> None:
	"""Refresh an OAuth access token when it has expired (per provider flow).

	Dropbox is intentionally absent: its SDK client auto-refreshes from the
	stored refresh token + app key/secret, so no pre-emptive refresh is needed.
	"""
	if not doc.token_expiry or get_datetime(doc.token_expiry) > now_datetime():
		return
	if doc.provider_type == "google_drive":
		oauth_service.refresh_token(doc)
	elif doc.provider_type == "onedrive":
		oauth2_service.refresh_onedrive(doc)


def _build_config(doc: Document) -> dict:
	"""Assemble the credential/destination config passed to the provider."""
	config = {
		"provider_type": doc.provider_type,
		"root_folder": doc.root_folder,
		"destination_folder": doc.destination_folder,
	}
	if doc.provider_type in OBJECT_PROVIDERS:
		config.update({"bucket": doc.bucket, "region": doc.region})
	else:
		config.update(
			{
				"access_token": doc.get_password("access_token", raise_exception=False),
				"refresh_token": doc.get_password("refresh_token", raise_exception=False),
			}
		)
		if doc.provider_type == "dropbox":
			# The Dropbox SDK needs the app key/secret to auto-refresh tokens.
			config.update(
				{
					"client_id": doc.get_password("client_id", raise_exception=False),
					"client_secret": doc.get_password("client_secret", raise_exception=False),
				}
			)
	return config
