# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""App constants not derivable from a DocType schema."""

from __future__ import annotations

UPLOAD_QUEUE = "long"
UPLOAD_TIMEOUT = 3600
UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024
UPLOAD_MAX_ATTEMPTS = 4
UPLOAD_BACKOFF_SECONDS = (2, 5, 10)

# Outbound provider-API request timeout for light metadata/connection calls.
HTTP_TIMEOUT = 30

# Fraction of quota used at/above which the dashboard warns (FR-29).
QUOTA_WARN_THRESHOLD = 0.9


class StorageKind:
	"""How a provider addresses backups: folder tree vs object store."""

	FOLDER = "folder"
	OBJECT = "object"


# Folder-vs-object is app domain knowledge, not part of the DocType schema.
PROVIDER_STORAGE_KIND: dict[str, str] = {
	"google_drive": StorageKind.FOLDER,
	"dropbox": StorageKind.FOLDER,
	"onedrive": StorageKind.FOLDER,
	"amazon_s3": StorageKind.OBJECT,
}
FOLDER_PROVIDERS: frozenset[str] = frozenset(
	t for t, kind in PROVIDER_STORAGE_KIND.items() if kind == StorageKind.FOLDER
)
OBJECT_PROVIDERS: frozenset[str] = frozenset(
	t for t, kind in PROVIDER_STORAGE_KIND.items() if kind == StorageKind.OBJECT
)


def storage_kind_for(provider_type: str | None) -> str:
	"""Return the StorageKind for provider_type, or '' when unknown."""
	return PROVIDER_STORAGE_KIND.get(provider_type or "", "")
