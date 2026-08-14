# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Whitelisted provider endpoints: authorize, test, browse/create folders."""

from __future__ import annotations

import frappe

from cloud_backup.services import oauth_service, provider_service
from cloud_backup.utils.exceptions import CloudBackupError


@frappe.whitelist()
def authorize(provider: str) -> dict[str, str]:
	"""Return the Google consent URL for the provider."""
	frappe.has_permission("Cloud Backup Provider", "write", doc=provider, throw=True)
	return oauth_service.get_authorization_url(provider)


@frappe.whitelist()
def test_connection(provider: str) -> dict:
	"""Test connectivity; always returns {ok, message} (never raises)."""
	frappe.has_permission("Cloud Backup Provider", "write", doc=provider, throw=True)
	try:
		return provider_service.get_provider(provider).test_connection()
	except CloudBackupError as exc:
		return {"ok": False, "message": exc.message or str(exc)}


@frappe.whitelist()
def list_folders(provider: str, parent_id: str | None = None) -> list[dict]:
	"""Return folders under parent_id for the provider destination browser."""
	frappe.has_permission("Cloud Backup Provider", "read", doc=provider, throw=True)
	try:
		return provider_service.get_provider(provider).list_folders(parent_id)
	except CloudBackupError as exc:
		frappe.throw(exc.message or str(exc), title=frappe._("Cloud Backup"))


@frappe.whitelist()
def create_folder(provider: str, name: str, parent_id: str | None = None) -> dict:
	"""Create a folder under parent_id and return its id/name."""
	frappe.has_permission("Cloud Backup Provider", "write", doc=provider, throw=True)
	try:
		return provider_service.get_provider(provider).create_folder(name, parent_id)
	except CloudBackupError as exc:
		frappe.throw(exc.message or str(exc), title=frappe._("Cloud Backup"))
