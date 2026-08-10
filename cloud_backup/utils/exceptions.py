# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Typed provider-error taxonomy (BRD §12)."""


class CloudBackupError(Exception):
	"""Base cloud backup error; carries retryable classification."""

	retryable: bool = False

	def __init__(self, message: str = "", *, retryable: bool | None = None) -> None:
		super().__init__(message)
		self.message = message
		if retryable is not None:
			self.retryable = retryable


class AuthenticationError(CloudBackupError):
	"""Invalid or expired credentials; requires re-authorization."""

	retryable = False


class PermissionDenied(CloudBackupError):
	"""Provider rejected the operation for lack of permission."""

	retryable = False


class NetworkError(CloudBackupError):
	"""Transient network/API failure; safe to retry with backoff."""

	retryable = True


class RateLimited(CloudBackupError):
	"""Provider rate limit hit; retry honoring Retry-After."""

	retryable = True

	def __init__(self, message: str = "", *, retry_after: int | None = None) -> None:
		super().__init__(message, retryable=True)
		self.retry_after = retry_after


class StorageQuotaExceeded(CloudBackupError):
	"""Remote storage quota exhausted; no retry until freed."""

	retryable = False


class InvalidConfiguration(CloudBackupError):
	"""Provider configuration is missing or invalid."""

	retryable = False
