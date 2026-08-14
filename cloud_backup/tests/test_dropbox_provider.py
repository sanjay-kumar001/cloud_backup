# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Unit tests for DropboxProvider (Dropbox v2 REST stubbed)."""

import unittest
from unittest.mock import patch

from cloud_backup.providers.dropbox.provider import DropboxProvider, _join
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
	p = DropboxProvider(config or {"root_folder": "", "access_token": "tok"})
	p._token = "tok"
	return p


class TestDropboxProvider(unittest.TestCase):
	def test_class_metadata(self):
		self.assertEqual(DropboxProvider.provider_type, "dropbox")
		self.assertEqual(DropboxProvider.storage_kind, StorageKind.FOLDER)

	def test_authenticate_requires_token(self):
		with self.assertRaises(AuthenticationError):
			DropboxProvider({}).authenticate()

	def test_test_connection_ok(self):
		with patch("cloud_backup.providers.dropbox.provider.requests.post") as post:
			post.return_value = _Resp(payload={"email": "ada@example.com"})
			result = _provider().test_connection()
		self.assertTrue(result["ok"])
		self.assertIn("ada@example.com", result["message"])

	def test_list_folders_filters_files(self):
		entries = {
			"entries": [
				{".tag": "folder", "name": "Backups", "path_lower": "/backups"},
				{".tag": "file", "name": "a.txt", "path_lower": "/a.txt"},
			]
		}
		with patch("cloud_backup.providers.dropbox.provider.requests.post") as post:
			post.return_value = _Resp(payload=entries)
			folders = _provider().list_folders()
		self.assertEqual(folders, [{"id": "/backups", "name": "Backups"}])

	def test_root_maps_to_empty_path(self):
		self.assertEqual(_provider()._resolve_parent("root"), "")
		self.assertEqual(_provider()._resolve_parent("/"), "")
		self.assertEqual(_provider()._resolve_parent("/backups"), "/backups")

	def test_join_paths(self):
		self.assertEqual(_join("", "f.sql.gz"), "/f.sql.gz")
		self.assertEqual(_join("/backups", "f.sql.gz"), "/backups/f.sql.gz")

	def test_storage_usage(self):
		with patch("cloud_backup.providers.dropbox.provider.requests.post") as post:
			post.return_value = _Resp(payload={"used": 30, "allocation": {"allocated": 100}})
			usage = _provider().get_storage_usage()
		self.assertEqual(usage, {"used": 30, "total": 100, "available": 70})

	def test_error_mapping(self):
		for status, exc in ((401, AuthenticationError), (403, PermissionDenied), (429, RateLimited), (503, NetworkError)):
			with patch("cloud_backup.providers.dropbox.provider.requests.post") as post:
				post.return_value = _Resp(status=status, payload={"error_summary": "bad"})
				with self.assertRaises(exc):
					_provider().delete_file("/x")
