# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Unit tests for AmazonS3Provider (boto3 S3 client stubbed)."""

import tempfile
import unittest

from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from cloud_backup.providers.amazon_s3.provider import AmazonS3Provider, _etag
from cloud_backup.utils.constants import StorageKind
from cloud_backup.utils.exceptions import (
	AuthenticationError,
	CloudBackupError,
	NetworkError,
	PermissionDenied,
	RateLimited,
)


class _FakePaginator:
	def __init__(self, pages):
		self._pages = pages

	def paginate(self, **kwargs):
		return iter(self._pages)


class _FakeClient:
	def __init__(self, pages=None, **handlers):
		self._pages = pages or []
		self._h = handlers

	def get_paginator(self, _name):
		return _FakePaginator(self._pages)

	def __getattr__(self, name):
		if name in self._h:
			return self._h[name]
		raise AttributeError(name)


def _provider(client=None, config=None):
	cfg = config or {"bucket": "my-bucket", "client_id": "AK", "client_secret": "sk", "region": "us-east-1"}
	p = AmazonS3Provider(cfg)
	p._client = client or _FakeClient()
	return p


def _client_error(code, status=None, op="HeadObject"):
	err = {"Error": {"Code": code}}
	if status:
		err["ResponseMetadata"] = {"HTTPStatusCode": status}
	return ClientError(err, op)


class TestAmazonS3Provider(unittest.TestCase):
	def test_class_metadata(self):
		self.assertEqual(AmazonS3Provider.provider_type, "amazon_s3")
		self.assertEqual(AmazonS3Provider.storage_kind, StorageKind.OBJECT)

	def test_authenticate_requires_keys(self):
		with self.assertRaises(AuthenticationError):
			AmazonS3Provider({"bucket": "b"}).authenticate()

	def test_resolve_prefix_normalization(self):
		p = _provider()
		self.assertEqual(p._resolve("root"), "")
		self.assertEqual(p._resolve("/"), "")
		self.assertEqual(p._resolve(""), "")
		self.assertEqual(p._resolve("backups"), "backups/")
		self.assertEqual(p._resolve("a/b/"), "a/b/")

	def test_test_connection_ok(self):
		client = _FakeClient(head_bucket=lambda **kw: {})
		result = _provider(client).test_connection()
		self.assertTrue(result["ok"])
		self.assertIn("my-bucket", result["message"])

	def test_test_connection_failure(self):
		def _boom(**kw):
			raise _client_error("AccessDenied", 403, "HeadBucket")

		result = _provider(_FakeClient(head_bucket=_boom)).test_connection()
		self.assertFalse(result["ok"])

	def test_list_folders_from_common_prefixes(self):
		pages = [{"CommonPrefixes": [{"Prefix": "backups/2026/"}, {"Prefix": "backups/2025/"}]}]
		p = _provider(_FakeClient(pages=pages))
		folders = p.list_folders("backups")
		self.assertEqual(folders, [{"id": "backups/2026/", "name": "2026"}, {"id": "backups/2025/", "name": "2025"}])

	def test_list_files_excludes_marker(self):
		pages = [
			{
				"Contents": [
					{"Key": "backups/", "Size": 0, "ETag": '"x"'},
					{"Key": "backups/db.sql.gz", "Size": 100, "ETag": '"abc"'},
				]
			}
		]
		p = _provider(_FakeClient(pages=pages))
		files = p.list_files("backups")
		self.assertEqual(files, [{"id": "backups/db.sql.gz", "name": "db.sql.gz", "size": 100, "checksum": "abc"}])

	def test_upload_file_returns_metadata(self):
		client = _FakeClient(
			upload_file=lambda *a, **kw: None,
			head_object=lambda **kw: {"ContentLength": 2048, "ETag": '"deadbeef"'},
		)
		with tempfile.NamedTemporaryFile(suffix=".sql.gz") as fh:
			fh.write(b"backup")
			fh.flush()
			out = _provider(client).upload_file(fh.name, "backups", "db.sql.gz")
		self.assertEqual(out["id"], "backups/db.sql.gz")
		self.assertEqual(out["name"], "db.sql.gz")
		self.assertEqual(out["size"], 2048)
		self.assertEqual(out["checksum"], "deadbeef")

	def test_get_file_metadata(self):
		client = _FakeClient(head_object=lambda **kw: {"ContentLength": 500, "ETag": '"h"'})
		meta = _provider(client).get_file_metadata("backups/db.sql.gz")
		self.assertEqual(meta, {"id": "backups/db.sql.gz", "name": "db.sql.gz", "size": 500, "checksum": "h"})

	def test_storage_usage_sums_sizes(self):
		pages = [{"Contents": [{"Key": "backups/a", "Size": 10}, {"Key": "backups/b", "Size": 32}]}]
		out = _provider(_FakeClient(pages=pages)).get_storage_usage()
		self.assertEqual(out, {"used": 42, "total": None, "available": None})

	def test_error_mapping(self):
		m = AmazonS3Provider._map
		self.assertIsInstance(m(NoCredentialsError()), AuthenticationError)
		self.assertIsInstance(m(EndpointConnectionError(endpoint_url="s3")), NetworkError)
		self.assertIsInstance(m(_client_error("AccessDenied", 403)), PermissionDenied)
		self.assertIsInstance(m(_client_error("SlowDown")), RateLimited)
		self.assertIsInstance(m(_client_error("NoSuchKey", 404)), CloudBackupError)
		self.assertIsInstance(m(ValueError("weird")), CloudBackupError)

	def test_etag_strips_quotes(self):
		self.assertEqual(_etag({"ETag": '"abc123"'}), "abc123")
		self.assertIsNone(_etag({}))
