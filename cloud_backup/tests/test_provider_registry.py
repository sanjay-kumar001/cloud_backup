# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Guard: registry classes and the storage-kind constants stay in sync."""

import unittest

from cloud_backup.providers.registry import PROVIDER_REGISTRY, get_provider_class
from cloud_backup.utils.constants import PROVIDER_STORAGE_KIND
from cloud_backup.utils.exceptions import InvalidConfiguration


class TestProviderRegistry(unittest.TestCase):
	def test_all_registered_types_match_key(self):
		for provider_type, cls in PROVIDER_REGISTRY.items():
			self.assertEqual(cls.provider_type, provider_type)

	def test_storage_kind_map_matches_registry(self):
		derived = {t: cls.storage_kind for t, cls in PROVIDER_REGISTRY.items()}
		self.assertEqual(derived, PROVIDER_STORAGE_KIND)

	def test_unknown_type_raises(self):
		with self.assertRaises(InvalidConfiguration):
			get_provider_class("mega")
