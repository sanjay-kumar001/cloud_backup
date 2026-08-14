# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Write operational Cloud Backup Log rows with secrets scrubbed."""

from __future__ import annotations

import json
import re

import frappe

# Field-name fragments whose values must never be logged (NFR-10/34).
_SECRET_KEYS = ("token", "secret", "password", "client_id", "api_key", "credential")
_REDACTED = "***"


def get_logger():
	"""Return the app's file logger (writes to logs/cloud_backup.log)."""
	return frappe.logger("cloud_backup", allow_site=True, file_count=10)


def write_log(
	event: str,
	message: str,
	level: str = "INFO",
	source: str = "",
	details: dict | None = None,
) -> str:
	"""Insert a Cloud Backup Log row + emit to the file logger. Never raises."""
	scrubbed = scrub_secrets(message)
	_emit_to_file(level, event, source, scrubbed)
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Cloud Backup Log",
				"event": event,
				"level": level,
				"source": source,
				"message": scrubbed,
				"details": json.dumps(scrub_secrets(details), indent=2, default=str) if details else None,
			}
		).insert(ignore_permissions=True)
		return doc.name
	except Exception:
		return ""


def _emit_to_file(level: str, event: str, source: str, message: str) -> None:
	"""Mirror the entry into logs/cloud_backup.log at the matching level."""
	try:
		logger = get_logger()
		line = f"[{source}] {event}: {message}"
		getattr(logger, {"ERROR": "error", "WARNING": "warning"}.get(level, "info"))(line)
	except Exception:
		pass


def scrub_secrets(value):
	"""Redact secret-looking keys in dicts and long token-like strings."""
	if isinstance(value, dict):
		return {k: (_REDACTED if _is_secret_key(k) else scrub_secrets(v)) for k, v in value.items()}
	if isinstance(value, list | tuple):
		return [scrub_secrets(v) for v in value]
	if isinstance(value, str):
		return _mask_tokens(value)
	return value


def _is_secret_key(key: str) -> bool:
	lowered = str(key).lower()
	return any(fragment in lowered for fragment in _SECRET_KEYS)


def _mask_tokens(text: str) -> str:
	"""Mask OAuth/bearer token-like substrings in free text."""
	return re.sub(r"ya29\.[\w.\-]+", _REDACTED, text)
