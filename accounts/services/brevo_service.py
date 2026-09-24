import os
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def get_brevo_config():
    api_key = os.getenv('BREVO_API_KEY') or os.getenv('Brevo')
    sender_email = os.getenv('BREVO_SENDER_EMAIL') or 'parasdhiman17y@gmail.com'
    sender_name = os.getenv('BREVO_SENDER_NAME') or 'Evento'
    return api_key, sender_email, sender_name


def send_otp_email(to_email: str, otp_code: str, recipient_name: str = "") -> tuple[bool, str]:
    """
    Sends a verification OTP email using Brevo (Sendinblue) Transactional API.
    Returns (success: bool, message: str)
    """
    api_key, sender_email, sender_name = get_brevo_config()

    if not api_key:
        logger.error("Brevo API key is not configured in environment variables.")
        return False, "Email service is temporarily unavailable (Missing API key)."

    greeting_name = recipient_name.strip() if recipient_name else "there"

    # Elegant HTML Email Template for Evento
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Evento Verification Code</title>
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #f7f7f8;
          margin: 0;
          padding: 0;
          color: #1c1917;
        }}
        .container {{
          max-width: 520px;
          margin: 32px auto;
          background: #ffffff;
          border-radius: 12px;
          border: 1px solid #e7e5e4;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }}
        .header {{
          background-color: #18181b;
          padding: 28px 32px;
          text-align: center;
        }}
        .header h1 {{
          color: #fafaf9;
          font-size: 24px;
          font-weight: 700;
          margin: 0;
          letter-spacing: -0.5px;
        }}
        .content {{
          padding: 36px 32px;
        }}
        .greeting {{
          font-size: 16px;
          color: #292524;
          margin-bottom: 12px;
        }}
        .intro {{
          font-size: 14px;
          color: #78716c;
          line-height: 1.6;
          margin-bottom: 24px;
        }}
        .otp-box {{
          background-color: #f5f5f4;
          border: 1.5px dashed #d6d3d1;
          border-radius: 8px;
          padding: 20px;
          text-align: center;
          margin: 24px 0;
        }}
        .otp-code {{
          font-family: 'Courier New', Courier, monospace;
          font-size: 32px;
          font-weight: 700;
          letter-spacing: 8px;
          color: #0c0a09;
          margin: 0;
        }}
        .meta-notice {{
          font-size: 12px;
          color: #a8a29e;
          text-align: center;
          margin-top: 10px;
        }}
        .warning {{
          background-color: #fef3c7;
          border-left: 4px solid #f59e0b;
          padding: 12px 16px;
          font-size: 13px;
          color: #92400e;
          border-radius: 4px;
          margin-top: 24px;
          line-height: 1.5;
        }}
        .footer {{
          padding: 20px 32px;
          background-color: #fafaf9;
          border-top: 1px solid #f5f5f4;
          text-align: center;
          font-size: 12px;
          color: #a8a29e;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>EVENTO</h1>
        </div>
        <div class="content">
          <p class="greeting">Hi {greeting_name},</p>
          <p class="intro">
            Welcome to Evento! Please use the 6-digit verification code below to complete your registration and activate your account.
          </p>
          
          <div class="otp-box">
            <div class="otp-code">{otp_code}</div>
            <div class="meta-notice">Valid for 5 minutes</div>
          </div>
          
          <div class="warning">
            <strong>Security Notice:</strong> Never share this OTP with anyone. Evento support will never ask for your verification code.
          </div>
        </div>
        <div class="footer">
          &copy; Evento Platform. If you did not request this email, please disregard it.
        </div>
      </div>
    </body>
    </html>
    """

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [
            {
                "email": to_email,
                "name": recipient_name or to_email.split("@")[0]
            }
        ],
        "subject": f"{otp_code} is your Evento verification code",
        "htmlContent": html_content
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"Brevo OTP email dispatched successfully to {to_email}")
            return True, "Verification code sent to your email."
        else:
            logger.error(f"Brevo API failed [{response.status_code}]: {response.text}")
            # Parse error message if available
            try:
                err_data = response.json()
                msg = err_data.get('message') or f"Brevo returned status {response.status_code}"
            except Exception:
                msg = response.text
            return False, f"Failed to send email: {msg}"
            
    except requests.RequestException as e:
        logger.error(f"Network error calling Brevo API: {str(e)}")
        return False, "Could not connect to email server. Please try again in a moment."


def send_password_reset_otp_email(to_email: str, otp_code: str, recipient_name: str = "") -> tuple[bool, str]:
    """
    Sends a one-time login / recovery OTP email using Brevo (Sendinblue) Transactional API.
    Returns (success: bool, message: str)
    """
    api_key, sender_email, sender_name = get_brevo_config()

    if not api_key:
        logger.error("Brevo API key is not configured in environment variables.")
        return False, "Email service is temporarily unavailable (Missing API key)."

    greeting_name = recipient_name.strip() if recipient_name else "there"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Evento One-Time Login Code</title>
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #f7f7f8;
          margin: 0;
          padding: 0;
          color: #1c1917;
        }}
        .container {{
          max-width: 520px;
          margin: 32px auto;
          background: #ffffff;
          border-radius: 12px;
          border: 1px solid #e7e5e4;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }}
        .header {{
          background-color: #18181b;
          padding: 28px 32px;
          text-align: center;
        }}
        .header h1 {{
          color: #fafaf9;
          font-size: 24px;
          font-weight: 700;
          margin: 0;
          letter-spacing: -0.5px;
        }}
        .content {{
          padding: 36px 32px;
        }}
        .greeting {{
          font-size: 16px;
          color: #292524;
          margin-bottom: 12px;
        }}
        .intro {{
          font-size: 14px;
          color: #78716c;
          line-height: 1.6;
          margin-bottom: 24px;
        }}
        .otp-box {{
          background-color: #f5f5f4;
          border: 1.5px dashed #d6d3d1;
          border-radius: 8px;
          padding: 20px;
          text-align: center;
          margin: 24px 0;
        }}
        .otp-code {{
          font-family: 'Courier New', Courier, monospace;
          font-size: 32px;
          font-weight: 700;
          letter-spacing: 8px;
          color: #0c0a09;
          margin: 0;
        }}
        .meta-notice {{
          font-size: 12px;
          color: #a8a29e;
          text-align: center;
          margin-top: 10px;
        }}
        .warning {{
          background-color: #fee2e2;
          border-left: 4px solid #ef4444;
          padding: 12px 16px;
          font-size: 13px;
          color: #991b1b;
          border-radius: 4px;
          margin-top: 24px;
          line-height: 1.5;
        }}
        .footer {{
          padding: 20px 32px;
          background-color: #fafaf9;
          border-top: 1px solid #f5f5f4;
          text-align: center;
          font-size: 12px;
          color: #a8a29e;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>EVENTO</h1>
        </div>
        <div class="content">
          <p class="greeting">Hi {greeting_name},</p>
          <p class="intro">
            We received a request to log in to your Evento account using a one-time verification code. Please use the 6-digit code below to sign in:
          </p>
          
          <div class="otp-box">
            <div class="otp-code">{otp_code}</div>
            <div class="meta-notice">Valid for 5 minutes</div>
          </div>
          
          <div class="warning">
            <strong>Security Notice:</strong> If you did not request this login code, please ignore this email or review your account security immediately. Never share this code with anyone.
          </div>
        </div>
        <div class="footer">
          &copy; Evento Platform. Secure Authentication Dispatch.
        </div>
      </div>
    </body>
    </html>
    """

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [
            {
                "email": to_email,
                "name": recipient_name or to_email.split("@")[0]
            }
        ],
        "subject": f"{otp_code} is your Evento login verification code",
        "htmlContent": html_content
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"Brevo login OTP email dispatched successfully to {to_email}")
            return True, "Login verification code sent to your email."
        else:
            logger.error(f"Brevo API failed [{response.status_code}]: {response.text}")
            try:
                err_data = response.json()
                msg = err_data.get('message') or f"Brevo returned status {response.status_code}"
            except Exception:
                msg = response.text
            return False, f"Failed to send email: {msg}"
            
    except requests.RequestException as e:
        logger.error(f"Network error calling Brevo API: {str(e)}")
        return False, "Could not connect to email server. Please try again in a moment."


def send_password_reset_link_email(to_email: str, reset_url: str, recipient_name: str = "") -> tuple[bool, str]:
    """
    Sends a secure password reset link email using Brevo (Sendinblue) Transactional API.
    Returns (success: bool, message: str)
    """
    api_key, sender_email, sender_name = get_brevo_config()

    if not api_key:
        logger.error("Brevo API key is not configured in environment variables.")
        return False, "Email service is temporarily unavailable (Missing API key)."

    greeting_name = recipient_name.strip() if recipient_name else "there"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Reset Your Evento Password</title>
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: #f7f7f8;
          margin: 0;
          padding: 0;
          color: #1c1917;
        }}
        .container {{
          max-width: 520px;
          margin: 32px auto;
          background: #ffffff;
          border-radius: 12px;
          border: 1px solid #e7e5e4;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }}
        .header {{
          background-color: #18181b;
          padding: 28px 32px;
          text-align: center;
        }}
        .header h1 {{
          color: #fafaf9;
          font-size: 24px;
          font-weight: 700;
          margin: 0;
          letter-spacing: -0.5px;
        }}
        .content {{
          padding: 36px 32px;
        }}
        .greeting {{
          font-size: 16px;
          color: #292524;
          margin-bottom: 12px;
        }}
        .intro {{
          font-size: 14px;
          color: #78716c;
          line-height: 1.6;
          margin-bottom: 24px;
        }}
        .button-wrapper {{
          text-align: center;
          margin: 28px 0;
        }}
        .btn {{
          display: inline-block;
          background-color: #18181b;
          color: #fafaf9 !important;
          text-decoration: none;
          padding: 14px 32px;
          border-radius: 8px;
          font-weight: 600;
          font-size: 15px;
          letter-spacing: 0.2px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }}
        .fallback {{
          font-size: 12px;
          color: #a8a29e;
          word-break: break-all;
          line-height: 1.5;
          margin-top: 20px;
          padding: 12px;
          background-color: #fafaf9;
          border-radius: 6px;
          border: 1px solid #f5f5f4;
        }}
        .warning {{
          background-color: #fee2e2;
          border-left: 4px solid #ef4444;
          padding: 12px 16px;
          font-size: 13px;
          color: #991b1b;
          border-radius: 4px;
          margin-top: 24px;
          line-height: 1.5;
        }}
        .footer {{
          padding: 20px 32px;
          background-color: #fafaf9;
          border-top: 1px solid #f5f5f4;
          text-align: center;
          font-size: 12px;
          color: #a8a29e;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>EVENTO</h1>
        </div>
        <div class="content">
          <p class="greeting">Hi {greeting_name},</p>
          <p class="intro">
            We received a request to reset your Evento password. Click the button below to choose a new password. This link will expire in <strong>15 minutes</strong>.
          </p>
          
          <div class="button-wrapper">
            <a href="{reset_url}" target="_blank" class="btn">Reset My Password</a>
          </div>
          
          <div class="fallback">
            If the button above does not work, copy and paste this link into your browser:<br/>
            <a href="{reset_url}" style="color: #18181b;">{reset_url}</a>
          </div>
          
          <div class="warning">
            <strong>Security Notice:</strong> If you did not request a password reset, please ignore this email or contact support if you suspect unauthorized access.
          </div>
        </div>
        <div class="footer">
          &copy; Evento Platform. Secure Authentication Dispatch.
        </div>
      </div>
    </body>
    </html>
    """

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [
            {
                "email": to_email,
                "name": recipient_name or to_email.split("@")[0]
            }
        ],
        "subject": "Reset your Evento account password",
        "htmlContent": html_content
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"Brevo password reset link email dispatched successfully to {to_email}")
            return True, "Password reset link sent to your email."
        else:
            logger.error(f"Brevo API failed [{response.status_code}]: {response.text}")
            try:
                err_data = response.json()
                msg = err_data.get('message') or f"Brevo returned status {response.status_code}"
            except Exception:
                msg = response.text
            return False, f"Failed to send email: {msg}"
            
    except requests.RequestException as e:
        logger.error(f"Network error calling Brevo API: {str(e)}")
        return False, "Could not connect to email server. Please try again in a moment."


