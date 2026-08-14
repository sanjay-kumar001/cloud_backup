# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Unit tests for OneDriveProvider (Graph REST stubbed)."""

import unittest
from unittest.mock import patch

from cloud_backup.providers.onedrive.provider import OneDriveProvider, _hash_of
from cloud_backup.utils.constants import StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	NetworkError,
	PermissionDenied,
	RateLimited,
)


class _Resp:
	def __init__(self, status=200, payload=None, headers=None):
		self.status_code = status
		self._payload = payload or {}
		self.headers = headers or {}
		self.content = b"x"

	@property
	def ok(self):
		return self.status_code < 400

	def json(self):
		return self._payload


def _provider(config=None):
	p = OneDriveProvider(config or {"root_folder": "root", "access_token": "tok"})
	p._token = "tok"
	return p


class TestOneDriveProvider(unittest.TestCase):
	def test_class_metadata(self):
		self.assertEqual(OneDriveProvider.provider_type, "onedrive")
		self.assertEqual(OneDriveProvider.storage_kind, StorageKind.FOLDER)

	def test_authenticate_requires_token(self):
		with self.assertRaises(AuthenticationError):
			OneDriveProvider({}).authenticate()

	def test_test_connection_ok(self):
		with patch("cloud_backup.providers.onedrive.provider.requests.request") as req:
			req.return_value = _Resp(payload={"displayName": "Ada"})
			result = _provider().test_connection()
		self.assertTrue(result["ok"])
		self.assertIn("Ada", result["message"])

	def test_list_folders_filters_files(self):
		page = {"value": [{"id": "1", "name": "Backups", "folder": {}}, {"id": "2", "name": "a.txt", "file": {}}]}
		with patch("cloud_backup.providers.onedrive.provider.requests.request") as req:
			req.return_value = _Resp(payload=page)
			folders = _provider().list_folders()
		self.assertEqual(folders, [{"id": "1", "name": "Backups"}])

	def test_create_folder_uses_root_children(self):
		with patch("cloud_backup.providers.onedrive.provider.requests.request") as req:
			req.return_value = _Resp(payload={"id": "n1", "name": "New"})
			out = _provider().create_folder("New", "root")
		self.assertEqual(out, {"id": "n1", "name": "New"})
		self.assertTrue(req.call_args[0][1].endswith("/root/children"))

	def test_storage_usage(self):
		with patch("cloud_backup.providers.onedrive.provider.requests.request") as req:
			req.return_value = _Resp(payload={"quota": {"total": 100, "used": 30, "remaining": 70}})
			usage = _provider().get_storage_usage()
		self.assertEqual(usage, {"used": 30, "total": 100, "available": 70})

	def test_error_mapping(self):
		for status, exc in ((401, AuthenticationError), (403, PermissionDenied), (429, RateLimited), (503, NetworkError)):
			with patch("cloud_backup.providers.onedrive.provider.requests.request") as req:
				req.return_value = _Resp(status=status, payload={"error": {"message": "bad"}})
				with self.assertRaises(exc):
					_provider().delete_file("x")

	def test_hash_prefers_sha256(self):
		item = {"file": {"hashes": {"sha256Hash": "abc", "quickXorHash": "xyz"}}}
		self.assertEqual(_hash_of(item), "abc")
