# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""OneDrive provider built on the Microsoft Graph v1.0 REST API."""

from __future__ import annotations

import os
from typing import Any

import requests
from requests.exceptions import RequestException

from cloud_backup.providers import errors
from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.providers.onedrive import GRAPH_BASE, GRAPH_CHUNK_SIZE, GRAPH_DRIVE
from cloud_backup.utils.constants import HTTP_TIMEOUT, UPLOAD_CHUNK_SIZE, StorageKind
from cloud_backup.utils.exceptions import AuthenticationError


class OneDriveProvider(CloudBackupProvider):
	"""Folder-based provider using Microsoft Graph and OneDrive."""

	provider_type = "onedrive"
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
			raise AuthenticationError("OneDrive provider is not authorized")
		self._token = token

	@property
	def token(self) -> str:
		if self._token is None:
			self.authenticate()
		return self._token

	def test_connection(self) -> dict[str, Any]:
		try:
			me = self._get(f"{GRAPH_BASE}/me")
			name = me.get("displayName") or me.get("userPrincipalName") or ""
			return {"ok": True, "message": f"Connected as {name}" if name else "Connected to OneDrive"}
		except Exception as exc:
			return {"ok": False, "message": getattr(exc, "message", None) or str(exc)}

	def list_folders(self, parent_id: str | None = None) -> list[dict[str, Any]]:
		children = self._children(self._resolve_parent(parent_id))
		return [{"id": c["id"], "name": c["name"]} for c in children if "folder" in c]

	def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
		parent = self._resolve_parent(parent_id)
		body = {"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
		created = self._post(f"{self._children_url(parent)}", json=body)
		return {"id": created["id"], "name": created["name"]}

	def upload_file(
		self, local_path: str, remote_target: str, remote_name: str | None = None
	) -> dict[str, Any]:
		parent = self._resolve_parent(remote_target)
		name = remote_name or os.path.basename(local_path)
		session = self._post(
			self._upload_session_url(parent, name),
			json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
		)
		item = self._upload_chunks(session["uploadUrl"], local_path)
		return {
			"id": item["id"],
			"name": item["name"],
			"size": int(item.get("size") or 0),
			"checksum": _hash_of(item),
		}

	def list_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
		parent = self._resolve_parent(folder_id or self.config.get("destination_folder"))
		return [
			{"id": c["id"], "name": c["name"], "size": int(c.get("size") or 0), "checksum": _hash_of(c)}
			for c in self._children(parent)
			if "file" in c
		]

	def get_file_metadata(self, file_id: str) -> dict[str, Any]:
		meta = self._get(f"{GRAPH_DRIVE}/items/{file_id}?$select=id,name,size,file")
		return {
			"id": meta["id"],
			"name": meta["name"],
			"size": int(meta.get("size") or 0),
			"checksum": _hash_of(meta),
		}

	def delete_file(self, file_id: str) -> None:
		self._request("DELETE", f"{GRAPH_DRIVE}/items/{file_id}")

	def download_file(self, file_id: str, local_path: str) -> str:
		response = self._request("GET", f"{GRAPH_DRIVE}/items/{file_id}/content", stream=True)
		with open(local_path, "wb") as handle:
			for chunk in response.iter_content(chunk_size=UPLOAD_CHUNK_SIZE):
				if chunk:
					handle.write(chunk)
		return local_path

	def get_storage_usage(self) -> dict[str, Any]:
		quota = self._get(f"{GRAPH_DRIVE}?$select=quota").get("quota", {})
		total = int(quota["total"]) if quota.get("total") is not None else None
		used = int(quota.get("used", 0))
		remaining = int(quota["remaining"]) if quota.get("remaining") is not None else None
		return {"used": used, "total": total, "available": remaining}

	def _children(self, parent: str) -> list[dict[str, Any]]:
		"""Return all child driveItems under parent, following pagination."""
		items: list[dict[str, Any]] = []
		url = f"{self._children_url(parent)}?$top=200"
		while url:
			page = self._get(url)
			items.extend(page.get("value", []))
			url = page.get("@odata.nextLink")
		return items

	def _upload_chunks(self, upload_url: str, local_path: str) -> dict[str, Any]:
		"""Stream local_path to a Graph upload session in Content-Range chunks."""
		total = os.path.getsize(local_path)
		sent = 0
		item: dict[str, Any] = {}
		with open(local_path, "rb") as handle:
			while sent < total:
				chunk = handle.read(GRAPH_CHUNK_SIZE)
				end = sent + len(chunk) - 1
				headers = {
					"Content-Length": str(len(chunk)),
					"Content-Range": f"bytes {sent}-{end}/{total}",
				}
				try:
					response = requests.put(
						upload_url, data=chunk, headers=headers, timeout=HTTP_TIMEOUT
					)
				except RequestException as exc:
					raise errors.map_exception(exc)
				if not response.ok:
					raise errors.map_response(response)
				sent = end + 1
				if self._progress and total:
					self._progress(sent / total)
				if response.status_code in (200, 201):
					item = response.json()
		return item

	def _resolve_parent(self, parent_id: str | None) -> str:
		return parent_id or self.config.get("root_folder") or "root"

	def _children_url(self, parent: str) -> str:
		return f"{GRAPH_DRIVE}/root/children" if parent == "root" else f"{GRAPH_DRIVE}/items/{parent}/children"

	def _upload_session_url(self, parent: str, name: str) -> str:
		anchor = "root" if parent == "root" else f"items/{parent}"
		return f"{GRAPH_DRIVE}/{anchor}:/{name}:/createUploadSession"

	def _get(self, url: str) -> dict[str, Any]:
		return self._request("GET", url).json()

	def _post(self, url: str, json: dict) -> dict[str, Any]:
		return self._request("POST", url, json=json).json()

	def _request(self, method: str, url: str, **kwargs) -> requests.Response:
		"""Issue an authenticated Graph request, mapping failures to typed errors."""
		headers = {"Authorization": f"Bearer {self.token}", **kwargs.pop("headers", {})}
		try:
			response = requests.request(
				method, url, headers=headers, timeout=kwargs.pop("timeout", HTTP_TIMEOUT), **kwargs
			)
		except RequestException as exc:
			raise errors.map_exception(exc)
		if not response.ok:
			raise errors.map_response(response)
		return response


def _hash_of(item: dict[str, Any]) -> str | None:
	"""Return the sha256 (business) or quickXor (personal) hash of a driveItem."""
	hashes = (item.get("file") or {}).get("hashes") or {}
	return hashes.get("sha256Hash") or hashes.get("quickXorHash")
