# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Amazon S3 provider on the official boto3 SDK; object keys are ids."""

from __future__ import annotations

import os
import threading
from typing import Any

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
	BotoCoreError,
	ClientError,
	EndpointConnectionError,
	NoCredentialsError,
	PartialCredentialsError,
)

from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.utils.constants import HTTP_TIMEOUT, UPLOAD_CHUNK_SIZE, StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	CloudBackupError,
	NetworkError,
	PermissionDenied,
	RateLimited,
	StorageQuotaExceeded,
)

_AUTH_CODES = {"InvalidAccessKeyId", "SignatureDoesNotMatch", "AccessDenied", "AccessDeniedException"}
_THROTTLE_CODES = {"SlowDown", "Throttling", "ThrottlingException", "RequestLimitExceeded"}
_NOTFOUND_CODES = {"NoSuchBucket", "NoSuchKey", "404", "NotFound"}


class AmazonS3Provider(CloudBackupProvider):
	"""Object-based provider; a prefix acts as a folder, a key as a file id."""

	provider_type = "amazon_s3"
	storage_kind = StorageKind.OBJECT

	def __init__(self, config: dict[str, Any]) -> None:
		super().__init__(config)
		self._client = None
		self._progress = None

	def set_progress_callback(self, callback) -> None:
		"""Register a callable(fraction: float) invoked during upload."""
		self._progress = callback

	def authenticate(self) -> None:
		key = self.config.get("client_id")
		secret = self.config.get("client_secret")
		if not (key and secret):
			raise AuthenticationError("Amazon S3 provider is missing access/secret key")
		self._client = boto3.client(
			"s3",
			aws_access_key_id=key,
			aws_secret_access_key=secret,
			region_name=self.config.get("region") or None,
			config=BotoConfig(connect_timeout=HTTP_TIMEOUT, retries={"max_attempts": 3}),
		)

	@property
	def client(self):
		if self._client is None:
			self.authenticate()
		return self._client

	@property
	def _bucket(self) -> str:
		bucket = self.config.get("bucket")
		if not bucket:
			raise CloudBackupError("Amazon S3 provider has no bucket configured")
		return bucket

	def test_connection(self) -> dict[str, Any]:
		try:
			self.client.head_bucket(Bucket=self._bucket)
			return {"ok": True, "message": f"Connected to bucket {self._bucket}"}
		except Exception as exc:
			mapped = self._map(exc)
			return {"ok": False, "message": mapped.message or str(mapped)}

	def list_folders(self, parent_id: str | None = None) -> list[dict[str, Any]]:
		prefix = self._resolve(parent_id)
		out: list[dict[str, Any]] = []
		for page in self._paginate(prefix, delimiter="/"):
			for cp in page.get("CommonPrefixes", []) or []:
				key = cp["Prefix"]
				out.append({"id": key, "name": key[len(prefix) :].rstrip("/")})
		return out

	def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
		key = f"{self._resolve(parent_id)}{name.strip('/')}/"
		try:
			self.client.put_object(Bucket=self._bucket, Key=key, Body=b"")
		except Exception as exc:
			raise self._map(exc)
		return {"id": key, "name": name.strip("/")}

	def upload_file(
		self, local_path: str, remote_target: str, remote_name: str | None = None
	) -> dict[str, Any]:
		name = remote_name or os.path.basename(local_path)
		key = f"{self._resolve(remote_target)}{name}"
		try:
			self._upload(local_path, key)
			meta = self.client.head_object(Bucket=self._bucket, Key=key)
		except Exception as exc:
			raise self._map(exc)
		return {
			"id": key,
			"name": name,
			"size": int(meta.get("ContentLength") or 0),
			"checksum": _etag(meta),
		}

	def list_files(self, folder_id: str | None = None) -> list[dict[str, Any]]:
		prefix = self._resolve(folder_id if folder_id is not None else self.config.get("destination_folder"))
		out: list[dict[str, Any]] = []
		for page in self._paginate(prefix, delimiter="/"):
			for obj in page.get("Contents", []) or []:
				key = obj["Key"]
				if key == prefix:
					continue
				out.append(
					{
						"id": key,
						"name": key[len(prefix) :],
						"size": int(obj.get("Size") or 0),
						"checksum": _etag(obj),
					}
				)
		return out

	def get_file_metadata(self, file_id: str) -> dict[str, Any]:
		try:
			meta = self.client.head_object(Bucket=self._bucket, Key=file_id)
		except Exception as exc:
			raise self._map(exc)
		return {
			"id": file_id,
			"name": file_id.rsplit("/", 1)[-1],
			"size": int(meta.get("ContentLength") or 0),
			"checksum": _etag(meta),
		}

	def delete_file(self, file_id: str) -> None:
		try:
			self.client.delete_object(Bucket=self._bucket, Key=file_id)
		except Exception as exc:
			raise self._map(exc)

	def download_file(self, file_id: str, local_path: str) -> str:
		try:
			self.client.download_file(self._bucket, file_id, local_path)
		except Exception as exc:
			raise self._map(exc)
		return local_path

	def get_storage_usage(self) -> dict[str, Any]:
		"""S3 has no account quota; report bytes managed under the prefix."""
		prefix = self._resolve(self.config.get("destination_folder"))
		used = 0
		try:
			for page in self._paginate(prefix, delimiter=None):
				for obj in page.get("Contents", []) or []:
					used += int(obj.get("Size") or 0)
		except Exception as exc:
			raise self._map(exc)
		return {"used": used, "total": None, "available": None}

	def _paginate(self, prefix: str, delimiter: str | None):
		"""Yield list_objects_v2 pages under prefix; raise mapped errors."""
		params: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
		if delimiter:
			params["Delimiter"] = delimiter
		try:
			yield from self.client.get_paginator("list_objects_v2").paginate(**params)
		except Exception as exc:
			raise self._map(exc)

	def _upload(self, local_path: str, key: str) -> None:
		"""Managed transfer; boto3 switches to multipart past the threshold."""
		size = os.path.getsize(local_path)
		transfer = TransferConfig(
			multipart_threshold=UPLOAD_CHUNK_SIZE,
			multipart_chunksize=UPLOAD_CHUNK_SIZE,
		)
		self.client.upload_file(
			local_path,
			self._bucket,
			key,
			Config=transfer,
			Callback=_ProgressProxy(self._progress, size),
		)

	def _resolve(self, parent_id: str | None) -> str:
		"""Normalize a folder id to an S3 prefix ('' for root, else 'a/b/')."""
		prefix = parent_id or self.config.get("root_folder") or ""
		if prefix in ("", "root", "/"):
			return ""
		return prefix.strip("/") + "/"

	@staticmethod
	def _map(exc: Exception) -> CloudBackupError:
		"""Map a boto3/botocore failure onto the typed error taxonomy."""
		if isinstance(exc, CloudBackupError):
			return exc
		if isinstance(exc, NoCredentialsError | PartialCredentialsError):
			return AuthenticationError(str(exc))
		if isinstance(exc, EndpointConnectionError):
			return NetworkError(str(exc))
		if isinstance(exc, ClientError):
			code = exc.response.get("Error", {}).get("Code", "")
			status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
			if code in _THROTTLE_CODES or status == 503:
				return RateLimited(str(exc))
			if code == "QuotaExceeded":
				return StorageQuotaExceeded(str(exc))
			if code in _AUTH_CODES or status in (401, 403):
				return PermissionDenied(str(exc))
			if code in _NOTFOUND_CODES:
				return CloudBackupError(str(exc))
			return CloudBackupError(str(exc))
		if isinstance(exc, BotoCoreError):
			return NetworkError(str(exc))
		return CloudBackupError(str(exc))


class _ProgressProxy:
	"""Accumulate boto3 per-chunk byte counts into a 0..1 fraction callback."""

	def __init__(self, callback, size: int) -> None:
		self._callback = callback
		self._size = size
		self._seen = 0
		self._lock = threading.Lock()

	def __call__(self, bytes_amount: int) -> None:
		if not self._callback or not self._size:
			return
		with self._lock:
			self._seen += bytes_amount
			self._callback(min(self._seen / self._size, 1.0))


def _etag(meta: dict) -> str | None:
	"""Return the S3 ETag without surrounding quotes."""
	etag = meta.get("ETag")
	return etag.strip('"') if etag else None
