# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Unit tests for DropboxProvider (official dropbox SDK client stubbed)."""

import types
import unittest

from dropbox import exceptions as dbx_exc
from dropbox.files import FileMetadata, FolderMetadata
from dropbox.users import IndividualSpaceAllocation, SpaceAllocation, SpaceUsage
from requests.exceptions import ConnectionError as ReqConnectionError

from cloud_backup.providers.dropbox.provider import DropboxProvider, _join
from cloud_backup.utils.constants import StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	CloudBackupError,
	NetworkError,
	RateLimited,
)


class _FakeClient:
	def __init__(self, **handlers):
		self._h = handlers

	def __getattr__(self, name):
		if name in self._h:
			return self._h[name]
		raise AttributeError(name)


def _provider(client=None, config=None):
	p = DropboxProvider(config or {"root_folder": "", "access_token": "tok"})
	p._client = client or _FakeClient()
	return p


class TestDropboxProvider(unittest.TestCase):
	def test_class_metadata(self):
		self.assertEqual(DropboxProvider.provider_type, "dropbox")
		self.assertEqual(DropboxProvider.storage_kind, StorageKind.FOLDER)

	def test_authenticate_requires_token(self):
		with self.assertRaises(AuthenticationError):
			DropboxProvider({}).authenticate()

	def test_test_connection_ok(self):
		client = _FakeClient(
			users_get_current_account=lambda: types.SimpleNamespace(email="ada@example.com")
		)
		result = _provider(client).test_connection()
		self.assertTrue(result["ok"])
		self.assertIn("ada@example.com", result["message"])

	def test_list_folders_filters_files(self):
		entries = [
			FolderMetadata(name="Backups", path_lower="/backups"),
			FileMetadata(name="a.txt", path_lower="/a.txt", size=10, content_hash="a" * 64),
		]
		page = types.SimpleNamespace(entries=entries, has_more=False, cursor="c")
		client = _FakeClient(files_list_folder=lambda path: page)
		folders = _provider(client).list_folders()
		self.assertEqual(folders, [{"id": "/backups", "name": "Backups"}])

	def test_root_maps_to_empty_path(self):
		self.assertEqual(_provider()._resolve("root"), "")
		self.assertEqual(_provider()._resolve("/"), "")
		self.assertEqual(_provider()._resolve("/backups"), "/backups")

	def test_resolve_prepends_leading_slash(self):
		# Dropbox rejects paths without a leading slash (folder ids may be stored bare).
		self.assertEqual(_provider()._resolve("avian_erp_backup"), "/avian_erp_backup")
		self.assertEqual(_join(_provider()._resolve("avian_erp_backup"), "db.sql.gz"), "/avian_erp_backup/db.sql.gz")

	def test_join_paths(self):
		self.assertEqual(_join("", "f.sql.gz"), "/f.sql.gz")
		self.assertEqual(_join("/backups", "f.sql.gz"), "/backups/f.sql.gz")

	def test_storage_usage(self):
		usage = SpaceUsage(
			used=30, allocation=SpaceAllocation.individual(IndividualSpaceAllocation(allocated=100))
		)
		client = _FakeClient(users_get_space_usage=lambda: usage)
		self.assertEqual(_provider(client).get_storage_usage(), {"used": 30, "total": 100, "available": 70})

	def test_error_mapping(self):
		m = DropboxProvider._map
		self.assertIsInstance(m(ReqConnectionError("boom")), NetworkError)
		self.assertIsInstance(m(RateLimited("x")), RateLimited)
		self.assertIsInstance(m(dbx_exc.RateLimitError("rid", backoff=7)), RateLimited)
		self.assertIsInstance(m(ValueError("weird")), CloudBackupError)
		self.assertEqual(m(RateLimited("x", retry_after=5)).retry_after, 5)
