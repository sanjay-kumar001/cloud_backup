# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Write operational Cloud Backup Log rows with secrets scrubbed."""

from __future__ import annotations

import json
import re

import frappe

from cloud_backup.utils.constants import DocType

# Field-name fragments whose values must never be logged (NFR-10/34).
_SECRET_KEYS = ("token", "secret", "password", "client_id", "api_key", "credential")
_REDACTED = "***"


def write_log(
	event: str,
	message: str,
	level: str = "INFO",
	source: str = "",
	details: dict | None = None,
) -> str:
	"""Insert a Cloud Backup Log row; details are secret-scrubbed. Never raises."""
	try:
		doc = frappe.get_doc(
			{
				"doctype": DocType.LOG,
				"event": event,
				"level": level,
				"source": source,
				"message": scrub_secrets(message),
				"details": json.dumps(scrub_secrets(details), indent=2, default=str) if details else None,
			}
		).insert(ignore_permissions=True)
		return doc.name
	except Exception:
		return ""


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
