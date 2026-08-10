# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Google Drive provider built on Frappe's GoogleOAuth service."""

from __future__ import annotations

from typing import Any

from googleapiclient.errors import HttpError
from requests.exceptions import RequestException

from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.providers.google_drive import (
	DRIVE_CALLBACK_METHOD,
	DRIVE_DOMAIN,
	DRIVE_SERVICE_VERSION,
	FOLDER_MIME_TYPE,
)
from cloud_backup.utils.constants import ProviderType, StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	CloudBackupError,
	NetworkError,
	PermissionDenied,
	RateLimited,
)

_UPLOAD_PENDING = "Google Drive file operations are not available yet"


class GoogleDriveProvider(CloudBackupProvider):
	"""Folder-based provider using the Google Drive v3 API."""

	provider_type = ProviderType.GOOGLE_DRIVE
	storage_kind = StorageKind.FOLDER

	def __init__(self, config: dict[str, Any]) -> None:
		super().__init__(config)
		self._service = None

	def authenticate(self) -> None:
		from frappe.integrations.google_oauth import GoogleOAuth

		access_token = self.config.get("access_token")
		refresh_token = self.config.get("refresh_token")
		if not access_token or not refresh_token:
			raise AuthenticationError("Google Drive provider is not authorized")
		oauth = GoogleOAuth(
			DRIVE_DOMAIN,
			config={
				"domain_callback_url": DRIVE_CALLBACK_METHOD,
				"service_version": DRIVE_SERVICE_VERSION,
			},
		)
		self._service = oauth.get_google_service_object(access_token, refresh_token)

	@property
	def service(self):
		if self._service is None:
			self.authenticate()
		return self._service

	def test_connection(self) -> dict[str, Any]:
		try:
			about = self.service.about().get(fields="user(emailAddress)").execute()
			email = about.get("user", {}).get("emailAddress", "")
			message = f"Connected as {email}" if email else "Connected to Google Drive"
			return {"ok": True, "message": message}
		except Exception as exc:
			return {"ok": False, "message": self._error_message(exc)}

	def list_folders(self, parent_id: str | None = None) -> list[dict[str, Any]]:
		parent = self._resolve_parent(parent_id)
		query = (
			f"mimeType='{FOLDER_MIME_TYPE}' and trashed=false and '{parent}' in parents"
		)
		try:
			response = (
				self.service.files()
				.list(
					q=query,
					fields="files(id,name)",
					orderBy="name",
					pageSize=200,
					spaces="drive",
				)
				.execute()
			)
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)
		return [{"id": f["id"], "name": f["name"]} for f in response.get("files", [])]

	def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
		parent = self._resolve_parent(parent_id)
		body = {"name": name, "mimeType": FOLDER_MIME_TYPE, "parents": [parent]}
		try:
			folder = self.service.files().create(body=body, fields="id,name").execute()
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)
		return {"id": folder["id"], "name": folder["name"]}

	def get_storage_usage(self) -> dict[str, Any]:
		try:
			quota = (
				self.service.about()
				.get(fields="storageQuota")
				.execute()
				.get("storageQuota", {})
			)
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)
		limit = int(quota["limit"]) if quota.get("limit") else None
		used = int(quota.get("usage", 0))
		return {"used": used, "total": limit, "available": (limit - used) if limit else None}

	def upload_file(self, local_path: str, remote_target: str) -> dict[str, Any]:
		raise NotImplementedError(_UPLOAD_PENDING)

	def list_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
		raise NotImplementedError(_UPLOAD_PENDING)

	def get_file_metadata(self, file_id: str) -> dict[str, Any]:
		raise NotImplementedError(_UPLOAD_PENDING)

	def delete_file(self, file_id: str) -> None:
		raise NotImplementedError(_UPLOAD_PENDING)

	def _resolve_parent(self, parent_id: str | None) -> str:
		return parent_id or self.config.get("root_folder") or "root"

	def _error_message(self, exc: Exception) -> str:
		mapped = self._map_error(exc)
		return mapped.message or str(exc)

	@staticmethod
	def _map_error(exc: Exception) -> CloudBackupError:
		"""Map a Drive/HTTP failure onto the typed error taxonomy."""
		if isinstance(exc, RequestException):
			return NetworkError(str(exc))
		status = getattr(getattr(exc, "resp", None), "status", None)
		detail = getattr(exc, "reason", None) or str(exc)
		if status == 401:
			return AuthenticationError(detail)
		if status == 403:
			return PermissionDenied(detail)
		if status == 429:
			return RateLimited(detail)
		if status and status >= 500:
			return NetworkError(detail)
		return CloudBackupError(detail)
