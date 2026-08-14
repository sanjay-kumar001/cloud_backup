# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Map REST/HTTP failures onto the typed error taxonomy (BRD §12)."""

from __future__ import annotations

from requests import Response
from requests.exceptions import RequestException

from cloud_backup.utils.exceptions import (
	AuthenticationError,
	CloudBackupError,
	NetworkError,
	PermissionDenied,
	RateLimited,
	StorageQuotaExceeded,
)


def map_status(status: int, detail: str = "", retry_after: int | None = None) -> CloudBackupError:
	"""Return the typed error for an HTTP status code."""
	if status in (401,):
		return AuthenticationError(detail)
	if status == 403:
		return PermissionDenied(detail)
	if status in (429,):
		return RateLimited(detail, retry_after=retry_after)
	if status == 507:
		return StorageQuotaExceeded(detail)
	if status >= 500:
		return NetworkError(detail)
	return CloudBackupError(detail)


def map_response(response: Response, detail: str = "") -> CloudBackupError:
	"""Map a failed requests.Response onto a typed error, honoring Retry-After."""
	retry_after = None
	raw = response.headers.get("Retry-After")
	if raw and raw.isdigit():
		retry_after = int(raw)
	return map_status(response.status_code, detail or _body_detail(response), retry_after)


def map_exception(exc: RequestException) -> CloudBackupError:
	"""Map a transport-level requests exception (no response) to NetworkError."""
	return NetworkError(str(exc))


def _body_detail(response: Response) -> str:
	"""Extract a short human error message from a JSON/text error body."""
	try:
		data = response.json()
	except ValueError:
		return (response.text or "")[:200]
	if isinstance(data, dict):
		err = data.get("error")
		if isinstance(err, dict):
			return str(err.get("message") or err.get("error_summary") or err)
		return str(data.get("error_summary") or data.get("error_description") or err or data)[:200]
	return str(data)[:200]
