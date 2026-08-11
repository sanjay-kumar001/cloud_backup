# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Background entrypoint that uploads one backup artifact."""

from __future__ import annotations

import time

import frappe
from frappe.utils import now_datetime

from cloud_backup.services import provider_service
from cloud_backup.services.backup_service import ARTIFACT_LABEL
from cloud_backup.utils.constants import DocType
from cloud_backup.utils.exceptions import InvalidConfiguration
from cloud_backup.utils.file_utils import build_remote_filename


def run(history: str, artifact: str | None = None, trigger: str = "manual") -> str:
	"""Upload the artifact referenced by a History row; persist every transition."""
	doc = frappe.get_doc(DocType.HISTORY, history)
	started = time.monotonic()
	_set(doc, status="Processing", started_at=now_datetime())
	try:
		provider_doc = frappe.get_doc(DocType.PROVIDER, doc.provider)
		target = provider_doc.destination_folder or provider_doc.root_folder
		if not target:
			raise InvalidConfiguration("Provider has no destination folder selected")
		remote_name = build_remote_filename(
			doc.site, ARTIFACT_LABEL.get(artifact, doc.backup_type), doc.local_file
		)
		provider = provider_service.get_provider(provider_doc)
		_set(doc, status="Uploading")
		result = provider.upload_file(doc.local_file, target, remote_name)
		_set(
			doc,
			status="Completed",
			remote_file=result.get("id"),
			remote_path=provider_doc.folder_name_display or target,
			file_size=result.get("size") or 0,
			checksum=result.get("checksum"),
			completed_at=now_datetime(),
			duration=round(time.monotonic() - started, 2),
		)
		_update_settings(True, f"Uploaded {remote_name}")
	except Exception as exc:
		message = getattr(exc, "message", None) or str(exc)
		_set(
			doc,
			status="Failed",
			error=message,
			completed_at=now_datetime(),
			duration=round(time.monotonic() - started, 2),
		)
		_update_settings(False, message)
		raise
	return doc.name


def _set(doc, **fields) -> None:
	"""Persist History field changes immediately and notify open forms."""
	for key, value in fields.items():
		doc.db_set(key, value, update_modified=True, commit=False)
	frappe.db.commit()
	frappe.publish_realtime(
		"cloud_backup_history_update",
		{"name": doc.name, "status": doc.status},
		doctype=DocType.HISTORY,
		docname=doc.name,
	)


def _update_settings(success: bool, message: str) -> None:
	"""Write the last-upload status trio back onto Settings."""
	frappe.db.set_value(
		DocType.SETTINGS,
		DocType.SETTINGS,
		{
			"last_upload_timestamp": now_datetime(),
			"last_upload_status": "Success" if success else "Failed",
			"last_upload_message": message,
		},
	)
	frappe.db.commit()
