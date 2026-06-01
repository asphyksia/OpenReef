import html
import httpx
import logging

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


async def send_verification_email(to_email: str, token: str) -> bool:
    """Send email verification link via Resend API.

    Returns True if the email was accepted by Resend, False otherwise.
    """
    if not settings.resend_api_key:
        logger.warning("No RESEND_API_KEY configured")
        return False

    verify_url = f"{settings.app_url}/verify?token={token}"
    # Escape URL to prevent XSS if app_url is misconfigured
    safe_url = html.escape(verify_url)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.email_from,
                    "to": [to_email],
                    "subject": "Verify your OpenReef account",
                    "html": f"""
                    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                        <h2>Welcome to OpenReef</h2>
                        <p>Thanks for signing up. Please verify your email address by clicking the button below:</p>
                        <a href="{safe_url}"
                           style="display: inline-block; padding: 12px 24px; background-color: #2563eb; color: #fff;
                                  text-decoration: none; border-radius: 6px; margin: 16px 0;">
                            Verify Email
                        </a>
                        <p style="color: #666; font-size: 14px;">
                            If the button doesn't work, paste this link into your browser:<br>
                            <a href="{safe_url}">{safe_url}</a>
                        </p>
                        <p style="color: #999; font-size: 12px; margin-top: 24px;">
                            This link expires in 24 hours. If you didn't create an OpenReef account, ignore this email.
                        </p>
                    </div>
                    """,
                },
            )
            if resp.status_code == 200:
                logger.info("Verification email sent to %s, response: %s", to_email, resp.json())
                return True
            else:
                logger.error(
                    "Resend API error for %s: status=%d, body=%s",
                    to_email, resp.status_code, resp.text,
                )
                return False
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", to_email, e)
        return False
