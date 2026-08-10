# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for the provider abstraction and registry."""

import unittest

from cloud_backup.providers.base import CloudBackupProvider
from cloud_backup.providers.registry import get_provider_class
from cloud_backup.utils.exceptions import InvalidConfiguration, NetworkError


class TestProviderAbstraction(unittest.TestCase):
	def test_base_is_abstract(self):
		with self.assertRaises(TypeError):
			CloudBackupProvider({})

	def test_registry_rejects_unknown_type(self):
		with self.assertRaises(InvalidConfiguration):
			get_provider_class("nope")

	def test_network_error_is_retryable(self):
		self.assertTrue(NetworkError().retryable)
