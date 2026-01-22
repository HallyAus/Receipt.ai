"""Google OAuth2 service for Gmail API access."""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Gmail API scopes - readonly for receipt extraction
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GoogleOAuthService:
    """Handle Google OAuth2 flow and token management."""

    @staticmethod
    def get_authorization_url(state: Optional[str] = None) -> str:
        """Generate OAuth2 authorization URL for Gmail access.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        if not settings.google_client_id or not settings.google_client_secret:
            raise ValueError("Google OAuth credentials not configured")

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GMAIL_SCOPES,
            redirect_uri=settings.google_redirect_uri,
        )

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )

        return authorization_url

    @staticmethod
    def exchange_code(code: str) -> Tuple[str, str, datetime, str, str]:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Tuple of (access_token, refresh_token, expires_at, email, account_id)
            Note: Tokens are returned but should NEVER be logged
        """
        if not settings.google_client_id or not settings.google_client_secret:
            raise ValueError("Google OAuth credentials not configured")

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GMAIL_SCOPES,
            redirect_uri=settings.google_redirect_uri,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user info
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()

        expires_at = datetime.utcnow() + timedelta(seconds=3600)  # Default 1 hour
        if credentials.expiry:
            expires_at = credentials.expiry.replace(tzinfo=None)

        return (
            credentials.token,
            credentials.refresh_token,
            expires_at,
            user_info.get("email"),
            user_info.get("id"),
        )

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Tuple[str, datetime]:
        """Refresh an expired access token.

        Args:
            refresh_token: The refresh token (decrypted)

        Returns:
            Tuple of (new_access_token, new_expires_at)
        """
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        # Force refresh
        from google.auth.transport.requests import Request

        credentials.refresh(Request())

        expires_at = datetime.utcnow() + timedelta(seconds=3600)
        if credentials.expiry:
            expires_at = credentials.expiry.replace(tzinfo=None)

        return credentials.token, expires_at

    @staticmethod
    def get_gmail_service(access_token: str, refresh_token: str):
        """Get authenticated Gmail API service.

        Args:
            access_token: Current access token
            refresh_token: Refresh token for auto-refresh

        Returns:
            Gmail API service object
        """
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        return build("gmail", "v1", credentials=credentials)
