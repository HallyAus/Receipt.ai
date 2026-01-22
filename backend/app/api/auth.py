"""Authentication routes for OAuth flows."""
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.models.account import MailAccount, MailProvider
from app.services.oauth_google import GoogleOAuthService
from app.services.oauth_microsoft import MicrosoftOAuthService

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# In-memory state storage for CSRF protection (use Redis in production)
_oauth_states: dict = {}


@router.get("/google")
async def google_auth_start():
    """Start Google OAuth flow - redirect to Google consent screen."""
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "google"

    auth_url = GoogleOAuthService.get_authorization_url(state=state)
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_auth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Handle Google OAuth callback."""
    if error:
        logger.error(f"Google OAuth error: {error}")
        return RedirectResponse(url=f"{settings.frontend_url}/accounts?error={error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Validate state for CSRF protection
    if state not in _oauth_states or _oauth_states.get(state) != "google":
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    del _oauth_states[state]

    try:
        # Exchange code for tokens
        access_token, refresh_token, expires_at, email, account_id = (
            GoogleOAuthService.exchange_code(code)
        )

        # Check if account already exists
        existing = await session.execute(
            select(MailAccount).where(
                MailAccount.provider == MailProvider.GMAIL,
                MailAccount.account_id == account_id,
            )
        )
        account = existing.scalar_one_or_none()

        if account:
            # Update tokens
            account.access_token = access_token
            account.refresh_token = refresh_token
            account.token_expires_at = expires_at
            account.email = email
        else:
            # Create new account
            account = MailAccount(
                provider=MailProvider.GMAIL,
                email=email,
                account_id=account_id,
                token_expires_at=expires_at,
            )
            account.access_token = access_token
            account.refresh_token = refresh_token
            session.add(account)

        await session.commit()

        logger.info(f"Successfully connected Gmail account: {email}")
        return RedirectResponse(url=f"{settings.frontend_url}/accounts?success=gmail")

    except Exception as e:
        logger.error(f"Google OAuth callback failed: {e}")
        return RedirectResponse(url=f"{settings.frontend_url}/accounts?error=oauth_failed")


@router.get("/microsoft")
async def microsoft_auth_start():
    """Start Microsoft OAuth flow - redirect to Microsoft consent screen."""
    if not settings.microsoft_client_id:
        raise HTTPException(status_code=503, detail="Microsoft OAuth not configured")

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "microsoft"

    auth_url = MicrosoftOAuthService.get_authorization_url(state=state)
    return RedirectResponse(url=auth_url)


@router.get("/microsoft/callback")
async def microsoft_auth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Handle Microsoft OAuth callback."""
    if error:
        logger.error(f"Microsoft OAuth error: {error} - {error_description}")
        return RedirectResponse(url=f"{settings.frontend_url}/accounts?error={error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Validate state for CSRF protection
    if state not in _oauth_states or _oauth_states.get(state) != "microsoft":
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    del _oauth_states[state]

    try:
        # Exchange code for tokens
        access_token, refresh_token, expires_at, email, account_id = (
            MicrosoftOAuthService.exchange_code(code)
        )

        # Check if account already exists
        existing = await session.execute(
            select(MailAccount).where(
                MailAccount.provider == MailProvider.MICROSOFT,
                MailAccount.account_id == account_id,
            )
        )
        account = existing.scalar_one_or_none()

        if account:
            # Update tokens
            account.access_token = access_token
            account.refresh_token = refresh_token
            account.token_expires_at = expires_at
            account.email = email
        else:
            # Create new account
            account = MailAccount(
                provider=MailProvider.MICROSOFT,
                email=email,
                account_id=account_id,
                token_expires_at=expires_at,
            )
            account.access_token = access_token
            account.refresh_token = refresh_token
            session.add(account)

        await session.commit()

        logger.info(f"Successfully connected Microsoft account: {email}")
        return RedirectResponse(url=f"{settings.frontend_url}/accounts?success=microsoft")

    except Exception as e:
        logger.error(f"Microsoft OAuth callback failed: {e}")
        return RedirectResponse(url=f"{settings.frontend_url}/accounts?error=oauth_failed")


@router.get("/status")
async def auth_status():
    """Get OAuth configuration status."""
    return {
        "google_configured": bool(settings.google_client_id and settings.google_client_secret),
        "microsoft_configured": bool(settings.microsoft_client_id and settings.microsoft_client_secret),
        "llm_enabled": settings.llm_enabled and bool(settings.openai_api_key),
    }
