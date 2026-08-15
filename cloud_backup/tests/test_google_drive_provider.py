# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Unit tests for GoogleDriveProvider (Drive API stubbed)."""

import tempfile
import unittest

from cloud_backup.providers.google_drive.provider import GoogleDriveProvider
from cloud_backup.utils.constants import StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	NetworkError,
	PermissionDenied,
	RateLimited,
)


class _Exec:
	def __init__(self, result):
		self._result = result

	def execute(self):
		return self._result

	def next_chunk(self):
		"""Single-chunk resumable upload: complete immediately."""
		return (None, self._result)


class _Files:
	def __init__(self, captured):
		self._captured = captured

	def list(self, **kwargs):
		self._captured["list"] = kwargs
		return _Exec({"files": [{"id": "f1", "name": "Backups"}]})

	def create(self, **kwargs):
		self._captured["create"] = kwargs
		return _Exec({"id": "new1", "name": kwargs["body"]["name"]})


class _About:
	def __init__(self, result):
		self._result = result

	def get(self, **kwargs):
		return _Exec(self._result)


class _FakeService:
	def __init__(self, about=None, captured=None):
		self._about = about or {"user": {"emailAddress": "me@example.com"}}
		self._captured = captured if captured is not None else {}

	def about(self):
		return _About(self._about)

	def files(self):
		return _Files(self._captured)


class _FakeHttpError(Exception):
	def __init__(self, status, reason="err"):
		super().__init__(reason)
		self.resp = type("R", (), {"status": status})()
		self.reason = reason


def _provider(service, config=None):
	p = GoogleDriveProvider(config or {"root_folder": "root"})
	p._service = service
	return p


class TestGoogleDriveProvider(unittest.TestCase):
	def test_class_metadata(self):
		self.assertEqual(GoogleDriveProvider.provider_type, "google_drive")
		self.assertEqual(GoogleDriveProvider.storage_kind, StorageKind.FOLDER)

	def test_authenticate_requires_tokens(self):
		with self.assertRaises(AuthenticationError):
			GoogleDriveProvider({}).authenticate()

	def test_test_connection_ok(self):
		result = _provider(_FakeService()).test_connection()
		self.assertTrue(result["ok"])
		self.assertIn("me@example.com", result["message"])

	def test_list_folders_query_and_parse(self):
		captured = {}
		folders = _provider(_FakeService(captured=captured), {"root_folder": "R"}).list_folders()
		self.assertEqual(folders, [{"id": "f1", "name": "Backups"}])
		self.assertIn("'R' in parents", captured["list"]["q"])
		self.assertIn("trashed=false", captured["list"]["q"])

	def test_create_folder(self):
		captured = {}
		out = _provider(_FakeService(captured=captured)).create_folder("New", "P")
		self.assertEqual(out, {"id": "new1", "name": "New"})
		self.assertEqual(captured["create"]["body"]["parents"], ["P"])

	def test_storage_usage(self):
		svc = _FakeService(about={"storageQuota": {"limit": "100", "usage": "30"}})
		usage = _provider(svc).get_storage_usage()
		self.assertEqual(usage, {"used": 30, "total": 100, "available": 70})

	def test_map_error_classification(self):
		m = GoogleDriveProvider._map_error
		self.assertIsInstance(m(_FakeHttpError(401)), AuthenticationError)
		self.assertIsInstance(m(_FakeHttpError(403)), PermissionDenied)
		self.assertIsInstance(m(_FakeHttpError(429)), RateLimited)
		self.assertIsInstance(m(_FakeHttpError(503)), NetworkError)

	def test_upload_file(self):
		captured = {}
		with tempfile.NamedTemporaryFile(suffix=".sql.gz") as fh:
			fh.write(b"backup")
			fh.flush()
			out = _provider(_FakeService(captured=captured)).upload_file(fh.name, "dest", "db.sql.gz")
		self.assertEqual(out["id"], "new1")
		self.assertEqual(out["name"], "db.sql.gz")
		self.assertEqual(captured["create"]["body"]["parents"], ["dest"])
