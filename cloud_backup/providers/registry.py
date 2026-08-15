# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Maps provider_type to its concrete provider class."""

from __future__ import annotations

from cloud_backup.providers.amazon_s3.provider import AmazonS3Provider
from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.providers.dropbox.provider import DropboxProvider
from cloud_backup.providers.google_drive.provider import GoogleDriveProvider
from cloud_backup.providers.onedrive.provider import OneDriveProvider
from cloud_backup.utils.exceptions import InvalidConfiguration

PROVIDER_REGISTRY: dict[str, type[CloudBackupProvider]] = {
	GoogleDriveProvider.provider_type: GoogleDriveProvider,
	OneDriveProvider.provider_type: OneDriveProvider,
	DropboxProvider.provider_type: DropboxProvider,
	AmazonS3Provider.provider_type: AmazonS3Provider,
}


def get_provider_class(provider_type: str) -> type[CloudBackupProvider]:
	"""Return the provider class for provider_type; raise if unregistered."""
	try:
		return PROVIDER_REGISTRY[provider_type]
	except KeyError:
		raise InvalidConfiguration(f"No provider registered for type '{provider_type}'")
