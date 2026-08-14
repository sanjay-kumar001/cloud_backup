# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Google Drive provider built on Frappe's GoogleOAuth service."""

from __future__ import annotations

import os
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from requests.exceptions import RequestException

from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.providers.google_drive import (
	DRIVE_CALLBACK_METHOD,
	DRIVE_DOMAIN,
	DRIVE_SERVICE_VERSION,
	FOLDER_MIME_TYPE,
	register_domain,
)
from cloud_backup.utils.constants import UPLOAD_CHUNK_SIZE, StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	CloudBackupError,
	NetworkError,
	PermissionDenied,
	RateLimited,
)


class GoogleDriveProvider(CloudBackupProvider):
	"""Folder-based provider using the Google Drive v3 API."""

	provider_type = "google_drive"
	storage_kind = StorageKind.FOLDER

	def __init__(self, config: dict[str, Any]) -> None:
		super().__init__(config)
		self._service = None
		self._progress = None

	def set_progress_callback(self, callback) -> None:
		"""Register a callable(fraction: float) invoked during upload."""
		self._progress = callback

	def authenticate(self) -> None:
		from frappe.integrations.google_oauth import GoogleOAuth

		access_token = self.config.get("access_token")
		refresh_token = self.config.get("refresh_token")
		if not access_token or not refresh_token:
			raise AuthenticationError("Google Drive provider is not authorized")
		register_domain()
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

	def upload_file(
		self, local_path: str, remote_target: str, remote_name: str | None = None
	) -> dict[str, Any]:
		parent = self._resolve_parent(remote_target)
		metadata = {"name": remote_name or os.path.basename(local_path), "parents": [parent]}
		media = MediaFileUpload(local_path, resumable=True, chunksize=UPLOAD_CHUNK_SIZE)
		try:
			request = self.service.files().create(
				body=metadata, media_body=media, fields="id,name,size,md5Checksum"
			)
			response = None
			while response is None:
				_status, response = request.next_chunk()
				if _status and self._progress:
					self._progress(_status.progress())
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)
		return {
			"id": response["id"],
			"name": response["name"],
			"size": int(response.get("size") or 0),
			"checksum": response.get("md5Checksum"),
		}

	def list_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
		parent = self._resolve_parent(folder_id or self.config.get("destination_folder"))
		query = f"trashed=false and mimeType!='{FOLDER_MIME_TYPE}' and '{parent}' in parents"
		try:
			response = (
				self.service.files()
				.list(q=query, fields="files(id,name,size,md5Checksum)", pageSize=1000, spaces="drive")
				.execute()
			)
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)
		return [
			{
				"id": f["id"],
				"name": f["name"],
				"size": int(f.get("size") or 0),
				"checksum": f.get("md5Checksum"),
			}
			for f in response.get("files", [])
		]

	def get_file_metadata(self, file_id: str) -> dict[str, Any]:
		try:
			meta = (
				self.service.files()
				.get(fileId=file_id, fields="id,name,size,md5Checksum")
				.execute()
			)
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)
		return {
			"id": meta["id"],
			"name": meta["name"],
			"size": int(meta.get("size") or 0),
			"checksum": meta.get("md5Checksum"),
		}

	def delete_file(self, file_id: str) -> None:
		try:
			self.service.files().delete(fileId=file_id).execute()
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)

	def download_file(self, file_id: str, local_path: str) -> str:
		from googleapiclient.http import MediaIoBaseDownload

		try:
			request = self.service.files().get_media(fileId=file_id)
			with open(local_path, "wb") as handle:
				downloader = MediaIoBaseDownload(handle, request, chunksize=UPLOAD_CHUNK_SIZE)
				done = False
				while not done:
					_status, done = downloader.next_chunk()
					if _status and self._progress:
						self._progress(_status.progress())
		except (HttpError, RequestException) as exc:
			raise self._map_error(exc)
		return local_path

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
