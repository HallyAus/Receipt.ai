"""Microsoft OAuth2 service for Microsoft Graph API access."""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import httpx
import msal

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Microsoft Graph scopes for mail access
GRAPH_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/User.Read",
    "offline_access",
]


class MicrosoftOAuthService:
    """Handle Microsoft OAuth2 flow and token management."""

    @staticmethod
    def _get_msal_app() -> msal.ConfidentialClientApplication:
        """Get MSAL application instance."""
        if not settings.microsoft_client_id or not settings.microsoft_client_secret:
            raise ValueError("Microsoft OAuth credentials not configured")

        authority = f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"

        return msal.ConfidentialClientApplication(
            settings.microsoft_client_id,
            authority=authority,
            client_credential=settings.microsoft_client_secret,
        )

    @staticmethod
    def get_authorization_url(state: Optional[str] = None) -> str:
        """Generate OAuth2 authorization URL for Microsoft Graph access.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        app = MicrosoftOAuthService._get_msal_app()

        auth_url = app.get_authorization_request_url(
            scopes=GRAPH_SCOPES,
            state=state,
            redirect_uri=settings.microsoft_redirect_uri,
        )

        return auth_url

    @staticmethod
    def exchange_code(code: str) -> Tuple[str, str, datetime, str, str]:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Tuple of (access_token, refresh_token, expires_at, email, account_id)
            Note: Tokens are returned but should NEVER be logged
        """
        app = MicrosoftOAuthService._get_msal_app()

        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=GRAPH_SCOPES,
            redirect_uri=settings.microsoft_redirect_uri,
        )

        if "error" in result:
            raise ValueError(f"Token exchange failed: {result.get('error_description', result.get('error'))}")

        access_token = result["access_token"]
        refresh_token = result.get("refresh_token", "")

        # Calculate expiration
        expires_in = result.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Get user info from Graph API
        user_info = MicrosoftOAuthService._get_user_info(access_token)

        return (
            access_token,
            refresh_token,
            expires_at,
            user_info.get("mail") or user_info.get("userPrincipalName"),
            user_info.get("id"),
        )

    @staticmethod
    def _get_user_info(access_token: str) -> dict:
        """Get user info from Microsoft Graph API."""
        with httpx.Client() as client:
            response = client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Tuple[str, str, datetime]:
        """Refresh an expired access token.

        Args:
            refresh_token: The refresh token (decrypted)

        Returns:
            Tuple of (new_access_token, new_refresh_token, new_expires_at)
        """
        app = MicrosoftOAuthService._get_msal_app()

        # MSAL doesn't have a direct refresh method, use the accounts cache approach
        # For refresh tokens, we need to use acquire_token_by_refresh_token
        result = app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=GRAPH_SCOPES,
        )

        if "error" in result:
            raise ValueError(f"Token refresh failed: {result.get('error_description', result.get('error'))}")

        expires_in = result.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return (
            result["access_token"],
            result.get("refresh_token", refresh_token),  # May return same token
            expires_at,
        )

    @staticmethod
    def get_graph_headers(access_token: str) -> dict:
        """Get headers for Microsoft Graph API requests.

        Args:
            access_token: Current access token

        Returns:
            Headers dict for API requests
        """
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
