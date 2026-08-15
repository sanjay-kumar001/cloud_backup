# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Dropbox provider on the official dropbox SDK (auto-refreshing client)."""

from __future__ import annotations

import os
from typing import Any

import dropbox
from dropbox import exceptions as dbx_exc
from dropbox.files import CommitInfo, FileMetadata, FolderMetadata, UploadSessionCursor, WriteMode
from requests.exceptions import RequestException

from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.utils.constants import HTTP_TIMEOUT, UPLOAD_CHUNK_SIZE, StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	CloudBackupError,
	NetworkError,
	RateLimited,
	StorageQuotaExceeded,
)


class DropboxProvider(CloudBackupProvider):
	"""Folder-based provider using the Dropbox v2 SDK; ids are paths."""

	provider_type = "dropbox"
	storage_kind = StorageKind.FOLDER

	def __init__(self, config: dict[str, Any]) -> None:
		super().__init__(config)
		self._client = None
		self._progress = None

	def set_progress_callback(self, callback) -> None:
		"""Register a callable(fraction: float) invoked during upload."""
		self._progress = callback

	def authenticate(self) -> None:
		access = self.config.get("access_token")
		refresh = self.config.get("refresh_token")
		if not (refresh or access):
			raise AuthenticationError("Dropbox provider is not authorized")
		# refresh_token + app_key/secret lets the SDK refresh access tokens itself.
		self._client = dropbox.Dropbox(
			oauth2_access_token=access,
			oauth2_refresh_token=refresh,
			app_key=self.config.get("client_id"),
			app_secret=self.config.get("client_secret"),
			timeout=HTTP_TIMEOUT,
		)

	@property
	def client(self):
		if self._client is None:
			self.authenticate()
		return self._client

	def test_connection(self) -> dict[str, Any]:
		try:
			account = self.client.users_get_current_account()
			email = getattr(account, "email", "")
			return {"ok": True, "message": f"Connected as {email}" if email else "Connected to Dropbox"}
		except Exception as exc:
			mapped = self._map(exc)
			return {"ok": False, "message": mapped.message or str(mapped)}

	def list_folders(self, parent_id: str | None = None) -> list[dict[str, Any]]:
		return [
			{"id": e.path_lower, "name": e.name}
			for e in self._entries(self._resolve(parent_id))
			if isinstance(e, FolderMetadata)
		]

	def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
		path = _join(self._resolve(parent_id), name)
		try:
			meta = self.client.files_create_folder_v2(path).metadata
		except Exception as exc:
			raise self._map(exc)
		return {"id": meta.path_lower, "name": meta.name}

	def upload_file(
		self, local_path: str, remote_target: str, remote_name: str | None = None
	) -> dict[str, Any]:
		name = remote_name or os.path.basename(local_path)
		path = _join(self._resolve(remote_target), name)
		try:
			meta = self._upload(local_path, path)
		except Exception as exc:
			raise self._map(exc)
		return {
			"id": meta.path_lower,
			"name": meta.name,
			"size": int(meta.size or 0),
			"checksum": meta.content_hash,
		}

	def list_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
		folder = self._resolve(folder_id or self.config.get("destination_folder"))
		return [
			{"id": e.path_lower, "name": e.name, "size": int(e.size or 0), "checksum": e.content_hash}
			for e in self._entries(folder)
			if isinstance(e, FileMetadata)
		]

	def get_file_metadata(self, file_id: str) -> dict[str, Any]:
		try:
			meta = self.client.files_get_metadata(file_id)
		except Exception as exc:
			raise self._map(exc)
		return {
			"id": meta.path_lower,
			"name": meta.name,
			"size": int(getattr(meta, "size", 0) or 0),
			"checksum": getattr(meta, "content_hash", None),
		}

	def delete_file(self, file_id: str) -> None:
		try:
			self.client.files_delete_v2(file_id)
		except Exception as exc:
			raise self._map(exc)

	def download_file(self, file_id: str, local_path: str) -> str:
		try:
			self.client.files_download_to_file(local_path, file_id)
		except Exception as exc:
			raise self._map(exc)
		return local_path

	def get_storage_usage(self) -> dict[str, Any]:
		try:
			usage = self.client.users_get_space_usage()
		except Exception as exc:
			raise self._map(exc)
		used = int(usage.used or 0)
		total = _allocated(usage.allocation)
		return {"used": used, "total": total, "available": (total - used) if total else None}

	def _entries(self, path: str) -> list[Any]:
		"""Return all entries under path, following Dropbox cursors."""
		try:
			result = self.client.files_list_folder(path)
			entries = list(result.entries)
			while result.has_more:
				result = self.client.files_list_folder_continue(result.cursor)
				entries.extend(result.entries)
		except Exception as exc:
			raise self._map(exc)
		return entries

	def _upload(self, local_path: str, path: str):
		"""Single-shot for small files, chunked upload session for large ones."""
		size = os.path.getsize(local_path)
		mode = WriteMode("overwrite")
		with open(local_path, "rb") as handle:
			if size <= UPLOAD_CHUNK_SIZE:
				meta = self.client.files_upload(handle.read(), path, mode=mode, mute=True)
				if self._progress:
					self._progress(1.0)
				return meta
			start = self.client.files_upload_session_start(handle.read(UPLOAD_CHUNK_SIZE))
			cursor = UploadSessionCursor(session_id=start.session_id, offset=handle.tell())
			commit = CommitInfo(path=path, mode=mode, mute=True)
			while size - handle.tell() > UPLOAD_CHUNK_SIZE:
				self.client.files_upload_session_append_v2(handle.read(UPLOAD_CHUNK_SIZE), cursor)
				cursor.offset = handle.tell()
				if self._progress and size:
					self._progress(cursor.offset / size)
			meta = self.client.files_upload_session_finish(handle.read(UPLOAD_CHUNK_SIZE), cursor, commit)
			if self._progress:
				self._progress(1.0)
			return meta

	def _resolve(self, parent_id: str | None) -> str:
		"""Dropbox root is the empty string; folders are absolute paths ('/name')."""
		parent = parent_id or self.config.get("root_folder") or ""
		if parent in ("", "root", "/"):
			return ""
		return parent if parent.startswith("/") else "/" + parent

	@staticmethod
	def _map(exc: Exception) -> CloudBackupError:
		"""Map an SDK/transport failure onto the typed error taxonomy."""
		if isinstance(exc, CloudBackupError):
			return exc
		if isinstance(exc, dbx_exc.AuthError):
			return AuthenticationError(str(exc))
		if isinstance(exc, dbx_exc.RateLimitError):
			return RateLimited(str(exc), retry_after=int(getattr(exc, "backoff", 0) or 0) or None)
		if isinstance(exc, dbx_exc.InternalServerError | dbx_exc.HttpError):
			return NetworkError(str(exc))
		if isinstance(exc, dbx_exc.ApiError):
			if "insufficient_space" in str(exc):
				return StorageQuotaExceeded(str(exc))
			return CloudBackupError(str(exc))
		if isinstance(exc, RequestException):
			return NetworkError(str(exc))
		return CloudBackupError(str(exc))


def _join(parent: str, name: str) -> str:
	"""Join a Dropbox parent path and a child name into an absolute path."""
	base = (parent or "").rstrip("/")
	return f"{base}/{name}"


def _allocated(allocation) -> int | None:
	"""Total bytes from a Dropbox SpaceAllocation union (individual/team)."""
	try:
		if allocation.is_individual():
			return int(allocation.get_individual().allocated)
		if allocation.is_team():
			return int(allocation.get_team().allocated)
	except Exception:
		return None
	return None
