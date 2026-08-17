# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Discover latest backups and enqueue upload jobs."""

from __future__ import annotations

import os

import frappe
from frappe.utils.backups import fetch_latest_backups

from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
	get_cloud_backup_settings,
	get_selected_artifacts,
)
from cloud_backup.utils.constants import UPLOAD_QUEUE, UPLOAD_TIMEOUT
from cloud_backup.utils.exceptions import InvalidConfiguration

# Backup artifacts to upload for each requested backup type.
TYPE_ARTIFACTS = {
	"database": ("database",),
	"files": ("public", "private"),
	"full": ("database", "public", "private"),
}

# Remote-filename label per artifact key.
ARTIFACT_LABEL = {"database": "database", "public": "files", "private": "private-files"}

# History backup_type recorded per artifact key.
ARTIFACT_TYPE = {"database": "database", "public": "files", "private": "files"}

# BackupGenerator path attribute per artifact key.
ARTIFACT_PATH_ATTR = {
	"database": "backup_path_db",
	"public": "backup_path_files",
	"private": "backup_path_private_files",
}

# Statuses that already own an upload for a local file (dedupe guard).
_ACTIVE_STATUSES = ("Queued", "Processing", "Uploading", "Verifying", "Completed")


def find_latest_backup() -> dict[str, str | None]:
	"""Return absolute paths of the latest {database, public, private} backups."""
	latest = fetch_latest_backups()
	return {"database": latest.get("database"), "public": latest.get("public"), "private": latest.get("private")}


def enqueue_upload(provider: str, backup_type: str, trigger: str = "manual") -> list[str]:
	"""Create Queued History rows for the latest backup and enqueue uploads."""
	if backup_type not in TYPE_ARTIFACTS:
		raise InvalidConfiguration(f"Unknown backup type '{backup_type}'")
	keys = TYPE_ARTIFACTS[backup_type]
	latest = find_latest_backup()
	# The most recent on-disk backup may be database-only; generate the missing
	# artifacts (incl. files) so the upload always honors the requested type.
	if any(not _exists(latest.get(key)) for key in keys):
		latest = _generate_backup(wants_files=bool({"public", "private"} & set(keys)))
	names: list[str] = []
	found = False
	for key in keys:
		path = latest.get(key)
		if not _exists(path):
			continue
		found = True
		# Dedupe against the after-backup auto-upload patch.
		if already_uploaded(path, provider):
			continue
		names.append(_create_and_enqueue(provider, backup_type, key, path, trigger))
	if not found:
		raise InvalidConfiguration("No backup file found to upload")
	return names


def _generate_backup(wants_files: bool) -> dict[str, str | None]:
	"""Create a fresh Frappe backup and return its artifact paths."""
	from frappe.utils.backups import new_backup

	odb = new_backup(ignore_files=not wants_files, force=True)
	return {
		"database": odb.backup_path_db,
		"public": odb.backup_path_files,
		"private": odb.backup_path_private_files,
	}


def _exists(path: str | None) -> bool:
	"""True when path is set and present on disk."""
	return bool(path and os.path.exists(path))


def enqueue_after_backup(odb, trigger: str = "auto") -> list[str]:
	"""Auto-upload entry (patch path): enqueue artifacts from a finished backup."""
	return _auto_enqueue(lambda artifact: getattr(odb, ARTIFACT_PATH_ATTR[artifact], None), trigger)


def auto_enqueue_latest(trigger: str = "fallback") -> list[str]:
	"""Auto-upload entry (fallback poller): enqueue artifacts from the latest backup."""
	latest = find_latest_backup()
	key = {"database": "database", "public": "public", "private": "private"}
	return _auto_enqueue(lambda artifact: latest.get(key[artifact]), trigger)


def enqueue_for_schedule(schedule, odb, trigger: str = "schedule") -> list[str]:
	"""Upload a schedule's backup to its provider, using the Settings backup types."""
	if not is_provider_ready(schedule.provider):
		return []
	artifacts = get_selected_artifacts()
	return _enqueue_artifacts(
		schedule.provider, artifacts, lambda a: getattr(odb, ARTIFACT_PATH_ATTR[a], None), trigger
	)


def resolve_provider(settings=None) -> str | None:
	"""Return the default provider if ready, else the fallback if ready, else None."""
	settings = settings or get_cloud_backup_settings()
	if settings.default_provider and is_provider_ready(settings.default_provider):
		return settings.default_provider
	if settings.fallback_provider and is_provider_ready(settings.fallback_provider):
		return settings.fallback_provider
	return None


def _auto_enqueue(path_for, trigger: str) -> list[str]:
	"""Settings-gated auto-upload of selected artifacts, with dedupe."""
	settings = get_cloud_backup_settings()
	if not (settings.enabled and settings.automatic_upload):
		return []
	provider = resolve_provider(settings)
	if not provider:
		return []
	return _enqueue_artifacts(provider, get_selected_artifacts(settings), path_for, trigger)


def _enqueue_artifacts(provider: str, artifacts, path_for, trigger: str) -> list[str]:
	"""Create + enqueue an upload per existing, not-yet-uploaded artifact."""
	names: list[str] = []
	for artifact in artifacts:
		path = path_for(artifact)
		if not path or not os.path.exists(path) or already_uploaded(path, provider):
			continue
		names.append(_create_and_enqueue(provider, ARTIFACT_TYPE[artifact], artifact, path, trigger))
	return names


def is_provider_ready(provider: str | None) -> bool:
	"""True when the provider is authorized and has a destination selected."""
	if not provider:
		return False
	config = frappe.db.get_value(
		"Cloud Backup Provider",
		provider,
		["authentication_status", "destination_folder", "root_folder"],
		as_dict=True,
	)
	return bool(
		config
		and config.authentication_status == "Authorized"
		and (config.destination_folder or config.root_folder)
	)


def already_uploaded(path: str, provider: str) -> bool:
	"""True when a History row already owns this file for this provider (NFR-06)."""
	return bool(
		frappe.db.exists(
			"Cloud Backup History",
			{"local_file": path, "provider": provider, "status": ["in", _ACTIVE_STATUSES]},
		)
	)


def upload_artifacts_sync(provider: str, artifacts, path_for, trigger: str = "cli") -> list[tuple[str, bool]]:
	"""Upload artifacts inline (for CLI); returns (history, ok) per artifact."""
	from cloud_backup.jobs import upload_backup

	results: list[tuple[str, bool]] = []
	for artifact in artifacts:
		path = path_for(artifact)
		if not path or not os.path.exists(path) or already_uploaded(path, provider):
			continue
		name = _create_history(provider, ARTIFACT_TYPE[artifact], artifact, path)
		try:
			upload_backup.run(name, artifact=artifact, trigger=trigger)
			results.append((name, True))
		except Exception:
			results.append((name, False))
	return results


def _create_and_enqueue(provider: str, backup_type: str, artifact: str, path: str, trigger: str) -> str:
	"""Create a Queued History row and enqueue its upload job."""
	name = _create_history(provider, backup_type, artifact, path)
	frappe.enqueue(
		"cloud_backup.jobs.upload_backup.run",
		queue=UPLOAD_QUEUE,
		timeout=UPLOAD_TIMEOUT,
		history=name,
		artifact=artifact,
		trigger=trigger,
	)
	return name


def _create_history(provider: str, backup_type: str, artifact: str, path: str) -> str:
	"""Insert a Queued History row and commit it (durable before enqueue)."""
	history = frappe.get_doc(
		{
			"doctype": "Cloud Backup History",
			"site": frappe.local.site,
			"provider": provider,
			"backup_type": backup_type,
			"local_file": path,
			"local_file_size": os.path.getsize(path),
			"status": "Queued",
		}
	).insert(ignore_permissions=True)
	# Commit before enqueue so the worker always sees the row — the CLI backup
	# path (bench backup) does not auto-commit like a web request (NFR-17).
	frappe.db.commit()
	return history.name
