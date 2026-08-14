# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Background entrypoint that uploads one backup artifact (retry + verify)."""

from __future__ import annotations

import time

import frappe
from frappe.utils import now_datetime

from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
	get_cloud_backup_settings,
)
from cloud_backup.services import log_service, notification_service, provider_service
from cloud_backup.services.backup_service import ARTIFACT_LABEL
from cloud_backup.utils.constants import UPLOAD_BACKOFF_SECONDS, UPLOAD_MAX_ATTEMPTS
from cloud_backup.utils.exceptions import CloudBackupError, InvalidConfiguration
from cloud_backup.utils.file_utils import build_remote_filename

SOURCE = "jobs.upload_backup"


def run(history: str, artifact: str | None = None, trigger: str = "manual") -> str:
	"""Upload the artifact referenced by a History row; persist every transition."""
	doc = frappe.get_doc("Cloud Backup History", history)
	started = time.monotonic()
	_set(doc, status="Processing", started_at=now_datetime())
	try:
		provider_doc = frappe.get_doc("Cloud Backup Provider", doc.provider)
		target = provider_doc.destination_folder or provider_doc.root_folder
		if not target:
			raise InvalidConfiguration("Provider has no destination folder selected")
		remote_name = build_remote_filename(
			doc.site, ARTIFACT_LABEL.get(artifact, doc.backup_type), doc.local_file
		)
		provider = provider_service.get_provider(provider_doc)
		_set(doc, status="Uploading")
		result = _upload_with_retry(doc, provider, target, remote_name)
		_set(
			doc,
			remote_file=result.get("id"),
			remote_path=provider_doc.folder_name_display or target,
			file_size=result.get("size") or 0,
			checksum=result.get("checksum"),
		)
		if get_cloud_backup_settings().verify_upload:
			_verify(doc, provider, result)
		_set(doc, status="Completed", completed_at=now_datetime(), duration=_elapsed(started))
		_update_settings(True, f"Uploaded {remote_name}")
		log_service.write_log("upload_completed", f"Uploaded {remote_name}", source=SOURCE)
	except Exception as exc:
		message = getattr(exc, "message", None) or str(exc)
		_set(doc, status="Failed", error=message, completed_at=now_datetime(), duration=_elapsed(started))
		_update_settings(False, message)
		log_service.write_log(
			"upload_failed", message, level="ERROR", source=SOURCE, details={"history": doc.name}
		)
		notification_service.notify(
			f"Cloud Backup failed: {doc.site}", f"Backup upload failed: {message}"
		)
		raise
	return doc.name


def _upload_with_retry(doc, provider, target: str, remote_name: str) -> dict:
	"""Upload with exponential backoff on retryable errors; fail fast otherwise."""
	for attempt in range(UPLOAD_MAX_ATTEMPTS):
		try:
			return provider.upload_file(doc.local_file, target, remote_name)
		except CloudBackupError as exc:
			if not exc.retryable or attempt == UPLOAD_MAX_ATTEMPTS - 1:
				raise
			wait = getattr(exc, "retry_after", None) or UPLOAD_BACKOFF_SECONDS[
				min(attempt, len(UPLOAD_BACKOFF_SECONDS) - 1)
			]
			_set(doc, status="Retrying", retry_count=(doc.retry_count or 0) + 1)
			log_service.write_log(
				"upload_retry",
				f"attempt {attempt + 1} failed, retrying in {wait}s: {exc}",
				level="WARNING",
				source=SOURCE,
			)
			time.sleep(wait)
			_set(doc, status="Uploading")
	raise CloudBackupError("Upload exhausted retries")  # defensive; unreachable


def _verify(doc, provider, result: dict) -> None:
	"""Compare remote size/checksum against the local artifact."""
	_set(doc, status="Verifying")
	try:
		meta = provider.get_file_metadata(result["id"])
	except CloudBackupError:
		_set(doc, verification_status="Failed")
		return
	size_ok = meta.get("size") and int(meta["size"]) == int(doc.local_file_size or 0)
	checksum_ok = not (result.get("checksum") and meta.get("checksum")) or result.get(
		"checksum"
	) == meta.get("checksum")
	verified = bool(size_ok and checksum_ok)
	_set(doc, verification_status="Verified" if verified else "Failed")
	if not verified:
		log_service.write_log(
			"verification_failed",
			f"remote size {meta.get('size')} vs local {doc.local_file_size}",
			level="WARNING",
			source=SOURCE,
		)


def _elapsed(started: float) -> float:
	return round(time.monotonic() - started, 2)


def _set(doc, **fields) -> None:
	"""Persist History field changes immediately and notify open forms."""
	for key, value in fields.items():
		doc.db_set(key, value, update_modified=True, commit=False)
	frappe.db.commit()
	frappe.publish_realtime(
		"cloud_backup_history_update",
		{"name": doc.name, "status": doc.status},
		doctype="Cloud Backup History",
		docname=doc.name,
	)


def _update_settings(success: bool, message: str) -> None:
	"""Write the last-upload status trio back onto Settings."""
	frappe.db.set_value(
		"Cloud Backup Settings",
		"Cloud Backup Settings",
		{
			"last_upload_timestamp": now_datetime(),
			"last_upload_status": "Success" if success else "Failed",
			"last_upload_message": message,
		},
	)
	frappe.db.commit()
