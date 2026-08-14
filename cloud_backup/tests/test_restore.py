# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Unit tests for restore_service (provider I/O mocked)."""

import types
import unittest

from cloud_backup.services import restore_service


class _FakeProvider:
	def __init__(self, name=None, raise_meta=False):
		self._name = name
		self._raise = raise_meta

	def get_file_metadata(self, file_id):
		if self._raise:
			raise RuntimeError("no metadata")
		return {"name": self._name}


class TestRestoreService(unittest.TestCase):
	def test_remote_filename_prefers_metadata(self):
		doc = types.SimpleNamespace(remote_file="id1", local_file="/x/db.sql.gz", name="CBH-1")
		self.assertEqual(
			restore_service._remote_filename(_FakeProvider(name="site_database_x.sql.gz"), doc),
			"site_database_x.sql.gz",
		)

	def test_remote_filename_falls_back_to_local_basename(self):
		doc = types.SimpleNamespace(remote_file="id1", local_file="/x/db.sql.gz", name="CBH-1")
		self.assertEqual(restore_service._remote_filename(_FakeProvider(raise_meta=True), doc), "db.sql.gz")

	def test_remote_filename_final_fallback(self):
		doc = types.SimpleNamespace(remote_file="id1", local_file=None, name="CBH-1")
		self.assertEqual(restore_service._remote_filename(_FakeProvider(raise_meta=True), doc), "CBH-1.bak")
