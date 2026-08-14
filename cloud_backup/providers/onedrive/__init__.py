# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""OneDrive (Microsoft Graph) endpoints and OAuth2 wiring constants."""

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_DRIVE = f"{GRAPH_BASE}/me/drive"

# 320 KiB multiple, required by Graph upload-session chunking.
GRAPH_CHUNK_SIZE = 5 * 320 * 1024

OAUTH2_CONFIG = {
	"authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
	"token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
	"scope": "offline_access Files.ReadWrite User.Read",
	"extra_authorize_params": {"response_mode": "query"},
}
