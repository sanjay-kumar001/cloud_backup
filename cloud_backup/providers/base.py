# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Provider abstraction (BRD §9.1); concrete providers subclass this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CloudBackupProvider(ABC):
	"""Common contract for all cloud storage providers."""

	# Concrete providers declare these; the registry derives the
	# provider_type -> storage_kind map from them (supersedes
	# utils.constants.PROVIDER_STORAGE_KIND once providers exist).
	provider_type: str = ""
	storage_kind: str = ""

	def __init__(self, config: dict[str, Any]) -> None:
		"""config: resolved credentials + destination, no Frappe DB access."""
		self.config = config

	@abstractmethod
	def authenticate(self) -> None:
		"""Establish an authenticated session; raise AuthenticationError on failure."""

	@abstractmethod
	def test_connection(self) -> dict[str, Any]:
		"""Return {ok: bool, message: str}; must not raise on expected failures."""

	@abstractmethod
	def list_folders(self, parent_id: str | None = None) -> list[dict[str, Any]]:
		"""Return folders under parent_id (or root when None)."""

	@abstractmethod
	def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
		"""Create a folder and return its metadata (id, name)."""

	@abstractmethod
	def upload_file(
		self, local_path: str, remote_target: str, remote_name: str | None = None
	) -> dict[str, Any]:
		"""Stream local_path into remote_target as remote_name; return id/name/size."""

	@abstractmethod
	def list_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
		"""Return files under folder_id (or the destination when None)."""

	@abstractmethod
	def get_file_metadata(self, file_id: str) -> dict[str, Any]:
		"""Return remote file metadata (size, checksum where available)."""

	@abstractmethod
	def delete_file(self, file_id: str) -> None:
		"""Delete the remote file identified by file_id."""

	@abstractmethod
	def get_storage_usage(self) -> dict[str, Any]:
		"""Return {used, total, available} where the provider exposes quota."""
