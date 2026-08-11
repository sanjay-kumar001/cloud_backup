# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for filename helpers."""

import unittest

from cloud_backup.utils.file_utils import build_remote_filename, file_extension, slugify_site


class TestFileUtils(unittest.TestCase):
	def test_file_extension_compound(self):
		self.assertEqual(file_extension("/b/x-database.sql.gz"), ".sql.gz")
		self.assertEqual(file_extension("/b/x-files.tar"), ".tar")
		self.assertEqual(file_extension("/b/noext"), "")

	def test_slugify_site(self):
		self.assertEqual(slugify_site("test.local"), "test_local")

	def test_build_remote_filename(self):
		name = build_remote_filename("test.local", "database", "/b/20260101-x-database.sql.gz")
		self.assertRegex(name, r"^test_local_database_\d{8}_\d{6}\.sql\.gz$")
