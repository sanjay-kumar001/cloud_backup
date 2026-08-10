# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Canonical provider-type identifiers and storage classification."""

from __future__ import annotations


class StorageKind:
	"""How a provider addresses backups: folder tree vs object store."""

	FOLDER = "folder"
	OBJECT = "object"


class ProviderType:
	"""Provider type identifiers; mirror the Cloud Backup Provider Select."""

	GOOGLE_DRIVE = "google_drive"
	DROPBOX = "dropbox"
	ONEDRIVE = "onedrive"
	AMAZON_S3 = "amazon_s3"


PROVIDER_STORAGE_KIND: dict[str, str] = {
	ProviderType.GOOGLE_DRIVE: StorageKind.FOLDER,
	ProviderType.DROPBOX: StorageKind.FOLDER,
	ProviderType.ONEDRIVE: StorageKind.FOLDER,
	ProviderType.AMAZON_S3: StorageKind.OBJECT,
}

PROVIDER_TYPES: tuple[str, ...] = tuple(PROVIDER_STORAGE_KIND)
FOLDER_PROVIDERS: frozenset[str] = frozenset(
	t for t, kind in PROVIDER_STORAGE_KIND.items() if kind == StorageKind.FOLDER
)
OBJECT_PROVIDERS: frozenset[str] = frozenset(
	t for t, kind in PROVIDER_STORAGE_KIND.items() if kind == StorageKind.OBJECT
)


def storage_kind_for(provider_type: str | None) -> str:
	"""Return the StorageKind for provider_type, or '' when unknown."""
	return PROVIDER_STORAGE_KIND.get(provider_type or "", "")
