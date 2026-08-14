# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Dropbox provider built on the Dropbox v2 REST API (path-addressed)."""

from __future__ import annotations

import json
import os
from typing import Any

import requests
from requests.exceptions import RequestException

from cloud_backup.providers import errors
from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.providers.dropbox import DROPBOX_CONTENT, DROPBOX_RPC
from cloud_backup.utils.constants import HTTP_TIMEOUT, UPLOAD_CHUNK_SIZE, StorageKind
from cloud_backup.utils.exceptions import AuthenticationError


class DropboxProvider(CloudBackupProvider):
	"""Folder-based provider using Dropbox v2; folder/file ids are paths."""

	provider_type = "dropbox"
	storage_kind = StorageKind.FOLDER

	def __init__(self, config: dict[str, Any]) -> None:
		super().__init__(config)
		self._token = None
		self._progress = None

	def set_progress_callback(self, callback) -> None:
		"""Register a callable(fraction: float) invoked during upload."""
		self._progress = callback

	def authenticate(self) -> None:
		token = self.config.get("access_token")
		if not token:
			raise AuthenticationError("Dropbox provider is not authorized")
		self._token = token

	@property
	def token(self) -> str:
		if self._token is None:
			self.authenticate()
		return self._token

	def test_connection(self) -> dict[str, Any]:
		try:
			account = self._rpc("/users/get_current_account")
			email = account.get("email", "")
			return {"ok": True, "message": f"Connected as {email}" if email else "Connected to Dropbox"}
		except Exception as exc:
			return {"ok": False, "message": getattr(exc, "message", None) or str(exc)}

	def list_folders(self, parent_id: str | None = None) -> list[dict[str, Any]]:
		return [
			{"id": e["path_lower"], "name": e["name"]}
			for e in self._list_folder(self._resolve_parent(parent_id))
			if e.get(".tag") == "folder"
		]

	def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
		path = _join(self._resolve_parent(parent_id), name)
		meta = self._rpc("/files/create_folder_v2", {"path": path}).get("metadata", {})
		return {"id": meta.get("path_lower", path), "name": meta.get("name", name)}

	def upload_file(
		self, local_path: str, remote_target: str, remote_name: str | None = None
	) -> dict[str, Any]:
		name = remote_name or os.path.basename(local_path)
		path = _join(self._resolve_parent(remote_target), name)
		meta = self._upload_session(local_path, path)
		return {
			"id": meta.get("path_lower", path),
			"name": meta.get("name", name),
			"size": int(meta.get("size") or 0),
			"checksum": meta.get("content_hash"),
		}

	def list_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
		folder = self._resolve_parent(folder_id or self.config.get("destination_folder"))
		return [
			{
				"id": e["path_lower"],
				"name": e["name"],
				"size": int(e.get("size") or 0),
				"checksum": e.get("content_hash"),
			}
			for e in self._list_folder(folder)
			if e.get(".tag") == "file"
		]

	def get_file_metadata(self, file_id: str) -> dict[str, Any]:
		meta = self._rpc("/files/get_metadata", {"path": file_id})
		return {
			"id": meta.get("path_lower", file_id),
			"name": meta.get("name"),
			"size": int(meta.get("size") or 0),
			"checksum": meta.get("content_hash"),
		}

	def delete_file(self, file_id: str) -> None:
		self._rpc("/files/delete_v2", {"path": file_id})

	def download_file(self, file_id: str, local_path: str) -> str:
		response = self._content("/files/download", {"path": file_id}, stream=True)
		with open(local_path, "wb") as handle:
			for chunk in response.iter_content(chunk_size=UPLOAD_CHUNK_SIZE):
				if chunk:
					handle.write(chunk)
		return local_path

	def get_storage_usage(self) -> dict[str, Any]:
		usage = self._rpc("/users/get_space_usage")
		used = int(usage.get("used", 0))
		allocation = usage.get("allocation", {})
		total = allocation.get("allocated")
		total = int(total) if total is not None else None
		return {"used": used, "total": total, "available": (total - used) if total else None}

	def _list_folder(self, path: str) -> list[dict[str, Any]]:
		"""Return all entries under path, following Dropbox cursors."""
		result = self._rpc("/files/list_folder", {"path": path})
		entries = list(result.get("entries", []))
		while result.get("has_more"):
			result = self._rpc("/files/list_folder/continue", {"cursor": result["cursor"]})
			entries.extend(result.get("entries", []))
		return entries

	def _upload_session(self, local_path: str, path: str) -> dict[str, Any]:
		"""Stream local_path to Dropbox via an upload session (any size)."""
		commit = {"path": path, "mode": "overwrite", "autorename": False, "mute": True}
		total = os.path.getsize(local_path)
		with open(local_path, "rb") as handle:
			data = handle.read(UPLOAD_CHUNK_SIZE)
			session_id = self._content("/files/upload_session/start", {"close": False}, data=data).json()[
				"session_id"
			]
			offset = len(data)
			while True:
				data = handle.read(UPLOAD_CHUNK_SIZE)
				cursor = {"session_id": session_id, "offset": offset}
				if len(data) < UPLOAD_CHUNK_SIZE:
					meta = self._content(
						"/files/upload_session/finish", {"cursor": cursor, "commit": commit}, data=data
					).json()
					if self._progress:
						self._progress(1.0)
					return meta
				self._content("/files/upload_session/append_v2", {"cursor": cursor}, data=data)
				offset += len(data)
				if self._progress and total:
					self._progress(offset / total)

	def _resolve_parent(self, parent_id: str | None) -> str:
		"""Dropbox root is the empty string; folders are absolute paths."""
		parent = parent_id or self.config.get("root_folder") or ""
		return "" if parent in ("", "root", "/") else parent

	def _rpc(self, endpoint: str, arg: dict | None = None) -> dict[str, Any]:
		"""Call a Dropbox RPC endpoint (JSON in, JSON out)."""
		kwargs = {"json": arg} if arg is not None else {}
		response = self._request(f"{DROPBOX_RPC}{endpoint}", **kwargs)
		return response.json() if response.content else {}

	def _content(self, endpoint: str, arg: dict, data: bytes = b"", stream: bool = False):
		"""Call a Dropbox content endpoint (binary body, args in header)."""
		headers = {
			"Dropbox-API-Arg": json.dumps(arg),
			"Content-Type": "application/octet-stream",
		}
		return self._request(f"{DROPBOX_CONTENT}{endpoint}", headers=headers, data=data, stream=stream)

	def _request(self, url: str, **kwargs) -> requests.Response:
		"""Issue an authenticated Dropbox POST, mapping failures to typed errors."""
		headers = {"Authorization": f"Bearer {self.token}", **kwargs.pop("headers", {})}
		try:
			response = requests.post(
				url, headers=headers, timeout=kwargs.pop("timeout", HTTP_TIMEOUT), **kwargs
			)
		except RequestException as exc:
			raise errors.map_exception(exc)
		if not response.ok:
			raise errors.map_response(response)
		return response


def _join(parent: str, name: str) -> str:
	"""Join a Dropbox parent path and a child name into an absolute path."""
	base = (parent or "").rstrip("/")
	return f"{base}/{name}"
