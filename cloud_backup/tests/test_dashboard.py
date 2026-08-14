# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Unit tests for dashboard_service aggregation (pure logic + mocked providers)."""

import types
import unittest
from unittest.mock import patch

from cloud_backup.services import dashboard_service
from cloud_backup.utils.exceptions import AuthenticationError


class TestDashboardService(unittest.TestCase):
	def test_utilization_percent_and_warn(self):
		out = dashboard_service._utilization({"used": 95, "total": 100, "available": 5})
		self.assertEqual(out["percent"], 0.95)
		self.assertTrue(out["warn"])

	def test_utilization_under_threshold(self):
		out = dashboard_service._utilization({"used": 10, "total": 100})
		self.assertEqual(out["percent"], 0.1)
		self.assertFalse(out["warn"])

	def test_utilization_unlimited_quota(self):
		out = dashboard_service._utilization({"used": 10, "total": None})
		self.assertIsNone(out["percent"])
		self.assertFalse(out["warn"])

	def test_health_states(self):
		disabled = types.SimpleNamespace(enabled=0, last_upload_status=None, default_provider="X")
		self.assertEqual(dashboard_service._health(disabled, 0), "Disabled")
		attention = types.SimpleNamespace(enabled=1, last_upload_status="Failed", default_provider="X")
		self.assertEqual(dashboard_service._health(attention, 3), "Attention")
		unconf = types.SimpleNamespace(enabled=1, last_upload_status="Success", default_provider=None)
		self.assertEqual(dashboard_service._health(unconf, 0), "Unconfigured")
		healthy = types.SimpleNamespace(enabled=1, last_upload_status="Success", default_provider="X")
		self.assertEqual(dashboard_service._health(healthy, 0), "Healthy")

	def test_get_storage_usage_maps_provider(self):
		fake = types.SimpleNamespace(get_storage_usage=lambda: {"used": 90, "total": 100, "available": 10})
		with patch.object(dashboard_service, "_authorized_providers", return_value=["Onedrive"]), patch.object(
			dashboard_service.provider_service, "get_provider", return_value=fake
		):
			out = dashboard_service.get_storage_usage()
		self.assertEqual(out[0]["provider"], "Onedrive")
		self.assertTrue(out[0]["ok"])
		self.assertTrue(out[0]["warn"])

	def test_get_storage_usage_handles_error(self):
		with patch.object(dashboard_service, "_authorized_providers", return_value=["Dropbox"]), patch.object(
			dashboard_service.provider_service, "get_provider", side_effect=AuthenticationError("nope")
		):
			out = dashboard_service.get_storage_usage()
		self.assertFalse(out[0]["ok"])
		self.assertIn("nope", out[0]["message"])
