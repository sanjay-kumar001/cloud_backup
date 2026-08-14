# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Download a cloud backup back to the site so it can be handed to Frappe restore."""

from __future__ import annotations

import os

import frappe

from cloud_backup.services import log_service, provider_service
from cloud_backup.utils.exceptions import InvalidConfiguration

SOURCE = "restore_service"


def download_backup(history: str) -> dict:
	"""Fetch a managed remote backup into the site's private/backups directory."""
	doc = frappe.get_doc("Cloud Backup History", history)
	if doc.status != "Completed" or not doc.remote_file:
		raise InvalidConfiguration("This history row has no completed remote upload to download")
	if doc.remote_deleted:
		raise InvalidConfiguration("The remote file for this backup was deleted")

	provider = provider_service.get_provider(doc.provider)
	filename = _remote_filename(provider, doc)
	dest_dir = frappe.get_site_path("private", "backups")
	os.makedirs(dest_dir, exist_ok=True)
	local_path = os.path.join(dest_dir, filename)

	provider.download_file(doc.remote_file, local_path)
	size = os.path.getsize(local_path)
	log_service.write_log(
		"restore_download",
		f"Downloaded {filename} ({size} bytes) from {doc.provider}",
		source=SOURCE,
		details={"history": doc.name},
	)
	return {"local_path": local_path, "filename": filename, "size": size, "backup_type": doc.backup_type}


def _remote_filename(provider, doc) -> str:
	"""Best-known filename for the downloaded artifact."""
	try:
		name = provider.get_file_metadata(doc.remote_file).get("name")
	except Exception:
		name = None
	if name:
		return os.path.basename(name)
	if doc.local_file:
		return os.path.basename(doc.local_file)
	return f"{doc.name}.bak"
