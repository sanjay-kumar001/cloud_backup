# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Dropbox API v2 endpoints and OAuth2 wiring constants."""

DROPBOX_RPC = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT = "https://content.dropboxapi.com/2"

OAUTH2_CONFIG = {
	"authorize_url": "https://www.dropbox.com/oauth2/authorize",
	"token_url": "https://api.dropboxapi.com/oauth2/token",
	"scope": "",
	# token_access_type=offline is what makes Dropbox issue a refresh token.
	"extra_authorize_params": {"token_access_type": "offline"},
}
