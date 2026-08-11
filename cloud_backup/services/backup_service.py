# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Discover latest backups and enqueue upload jobs."""

from __future__ import annotations

import os

import frappe
from frappe.utils.backups import fetch_latest_backups

from cloud_backup.utils.constants import UPLOAD_QUEUE, UPLOAD_TIMEOUT, DocType
from cloud_backup.utils.exceptions import InvalidConfiguration

# Backup artifacts to upload for each requested backup type.
TYPE_ARTIFACTS = {
	"database": ("database",),
	"files": ("public", "private"),
	"full": ("database", "public", "private"),
}

# Remote-filename label per artifact key.
ARTIFACT_LABEL = {"database": "database", "public": "files", "private": "private-files"}


def find_latest_backup() -> dict[str, str | None]:
	"""Return absolute paths of the latest {database, public, private} backups."""
	latest = fetch_latest_backups()
	return {"database": latest.get("database"), "public": latest.get("public"), "private": latest.get("private")}


def enqueue_upload(provider: str, backup_type: str, trigger: str = "manual") -> list[str]:
	"""Create Queued History rows for the latest backup and enqueue uploads."""
	if backup_type not in TYPE_ARTIFACTS:
		raise InvalidConfiguration(f"Unknown backup type '{backup_type}'")
	latest = find_latest_backup()
	names: list[str] = []
	for key in TYPE_ARTIFACTS[backup_type]:
		path = latest.get(key)
		if not path or not os.path.exists(path):
			continue
		history = frappe.get_doc(
			{
				"doctype": DocType.HISTORY,
				"site": frappe.local.site,
				"provider": provider,
				"backup_type": backup_type,
				"local_file": path,
				"local_file_size": os.path.getsize(path),
				"status": "Queued",
			}
		).insert(ignore_permissions=True)
		frappe.enqueue(
			"cloud_backup.jobs.upload_backup.run",
			queue=UPLOAD_QUEUE,
			timeout=UPLOAD_TIMEOUT,
			history=history.name,
			artifact=key,
			trigger=trigger,
		)
		names.append(history.name)
	if not names:
		raise InvalidConfiguration("No backup file found to upload")
	return names
