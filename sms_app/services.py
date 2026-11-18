import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

from sms_project.settings import parse_positive_int
from .models import format_status_label

TEXTBEE_DEFAULT_BASE_URL = 'https://api.textbee.dev/api/v1/gateway'
TEXTBEE_DEFAULT_SEND_URL = f'{TEXTBEE_DEFAULT_BASE_URL}/send-sms'

PLACEHOLDER_API_KEYS = {
    '',
    'replace_me',
    'your_api_key',
    'replace-with-textbee-api-key',
    'changeme',
    'none',
}
PLACEHOLDER_DEVICE_IDS = {
    '',
    'replace_me',
    'your_device_id',
    'replace-with-textbee-device-id',
    'changeme',
    'none',
}

AUTH_FAILURE_PHRASES = (
    'unauthenticated',
    'invalid api key',
    'api key is invalid',
    'invalid x-api-key',
    'missing api key',
    'invalid token',
    'expired api key',
)
QUOTA_ERROR_PHRASES = (
    'quota',
    'rate limit',
    'daily limit',
    'monthly limit',
    'limit exceeded',
    'limit reached',
    'plan limit',
    'too many requests',
    'insufficient credits',
)
DEVICE_NOT_FOUND_PHRASES = (
    'device not found',
    'invalid device',
    'device does not exist',
    'unknown device',
    'no device found',
    'invalid deviceid',
)
DEVICE_UNAVAILABLE_PHRASES = (
    'device is disabled',
    'disabled',
    'not enabled',
    'offline',
    'not connected',
    'disconnected',
    'fcm',
    'not reachable',
)
PERMISSION_ERROR_PHRASES = (
    'permission',
    'send_sms',
    'not allowed',
    'forbidden',
    'not authorized',
    'unauthorized',
)


@dataclass(frozen=True)
class SMSResult:
    """Structured outcome of an SMS send attempt via TextBee."""

    success: bool
    status_category: str
    provider_status: str
    user_message: str
    recipient_formatted: Optional[str] = None
    message_id: Optional[str] = None

    @property
    def status_label(self) -> str:
        """User-friendly status label for UI banners."""
        return format_status_label(self.provider_status)


@dataclass(frozen=True)
class TextBeeDiagnosticResult:
    """Structured outcome of safe read-only TextBee account and device diagnostics."""

    success: bool
    status_category: str
    provider_status: str
    user_message: str
    stats_status_code: Optional[int] = None
    devices_status_code: Optional[int] = None
    total_devices: Optional[int] = None
    total_sent_sms: Optional[int] = None
    device_found: bool = False
    device_enabled: bool = False
    device_name: Optional[str] = None


def format_textbee_recipient(recipient: str) -> str:
    """
    Preserve international E.164 phone numbers with the leading '+' (e.g., '+639171234567').
    If a Philippine number without '+' ('639XXXXXXXXX' or '09XXXXXXXXX') is passed directly,
    normalize it to '+639XXXXXXXXX'.
    """
    cleaned = (recipient or '').strip().replace(' ', '').replace('-', '')
    if cleaned.startswith('+'):
        return cleaned
    if cleaned.startswith('639') and len(cleaned) == 12 and cleaned.isdigit():
        return f'+{cleaned}'
    if cleaned.startswith('09') and len(cleaned) == 11 and cleaned.isdigit():
        return f'+63{cleaned[1:]}'
    return f'+{cleaned}' if cleaned.isdigit() else cleaned


def _get_api_key() -> str:
    key = (
        getattr(settings, 'TEXTBEE_API_KEY', None)
        if hasattr(settings, 'TEXTBEE_API_KEY')
        else os.environ.get('TEXTBEE_API_KEY', '')
    )
    return (key or '').strip()


def _get_device_id() -> str:
    device_id = (
        getattr(settings, 'TEXTBEE_DEVICE_ID', None)
        if hasattr(settings, 'TEXTBEE_DEVICE_ID')
        else os.environ.get('TEXTBEE_DEVICE_ID', '')
    )
    return (device_id or '').strip()


def _get_base_url() -> str:
    base_url = getattr(settings, 'TEXTBEE_BASE_URL', TEXTBEE_DEFAULT_BASE_URL) or TEXTBEE_DEFAULT_BASE_URL
    return base_url.strip().rstrip('/')


def _get_timeout_seconds() -> int:
    raw = (
        getattr(settings, 'TEXTBEE_TIMEOUT_SECONDS', None)
        if hasattr(settings, 'TEXTBEE_TIMEOUT_SECONDS')
        else os.environ.get('TEXTBEE_TIMEOUT_SECONDS')
    )
    return parse_positive_int(raw, default=10)


def is_textbee_configured() -> bool:
    """Return True when both TEXTBEE_API_KEY and TEXTBEE_DEVICE_ID are set to non-placeholder values."""
    api_key = _get_api_key().lower()
    device_id = _get_device_id().lower()
    return (api_key not in PLACEHOLDER_API_KEYS) and (device_id not in PLACEHOLDER_DEVICE_IDS)


def _extract_error_message(body: Any) -> str:
    """Extract error text from NestJS/TextBee JSON responses safely for internal classification."""
    if not isinstance(body, dict):
        return ''
    parts: List[str] = []
    for key in ('message', 'error', 'detail'):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
        elif isinstance(val, list):
            parts.extend(str(item).strip() for item in val if item)
    data = body.get('data')
    if isinstance(data, dict):
        for key in ('message', 'error'):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
    return ' '.join(parts)


def _classify_textbee_error(status_code: int, provider_error_text: str) -> SMSResult:
    """
    Classify HTTP status codes and TextBee error descriptions accurately without
    exposing API keys, device IDs, or raw provider stack traces:
    1. Explicit authentication failure (HTTP 401 or invalid API key message).
    2. Quota or rate limit errors (HTTP 402/429 or quota/limit message).
    3. Device not found / invalid device ID (HTTP 404 or device-not-found message).
    4. Disabled or offline Android device.
    5. Missing SMS or API permissions (HTTP 403 or permission message).
    6. Generic provider rejection fallback.
    """
    lowered = (provider_error_text or '').strip().lower()

    # 1. Explicit authentication failure
    if status_code == 401 or any(phrase in lowered for phrase in AUTH_FAILURE_PHRASES):
        return SMSResult(
            success=False,
            status_category='auth_error',
            provider_status='authentication_failed',
            user_message=(
                'Authentication with TextBee failed. Please verify that your '
                'TEXTBEE_API_KEY is valid and active (and restart the server after updating .env).'
            ),
        )

    # 2. Quota or rate limit exceeded
    if status_code in (402, 429) or any(phrase in lowered for phrase in QUOTA_ERROR_PHRASES):
        return SMSResult(
            success=False,
            status_category='quota_error',
            provider_status='quota_exceeded',
            user_message=(
                'Unable to send SMS: Your TextBee account quota or rate limit has been reached.'
            ),
        )

    # 3. Device not found or invalid Device ID
    if status_code == 404 or any(phrase in lowered for phrase in DEVICE_NOT_FOUND_PHRASES):
        return SMSResult(
            success=False,
            status_category='invalid_device',
            provider_status='device_not_found',
            user_message=(
                'The configured TextBee Device ID was not found on your account. '
                'Please verify TEXTBEE_DEVICE_ID in your environment configuration.'
            ),
        )

    # 4. Disabled or offline Android gateway device
    if any(phrase in lowered for phrase in DEVICE_UNAVAILABLE_PHRASES):
        return SMSResult(
            success=False,
            status_category='device_unavailable',
            provider_status='device_offline_or_disabled',
            user_message=(
                'The configured Android gateway device is disabled or offline in TextBee. '
                'Please open the TextBee Android app, ensure the device is enabled, and check its connection.'
            ),
        )

    # 5. Permission denied (HTTP 403 or Android/API permission issue)
    if status_code == 403 or any(phrase in lowered for phrase in PERMISSION_ERROR_PHRASES):
        return SMSResult(
            success=False,
            status_category='permission_error',
            provider_status='permission_denied',
            user_message=(
                'TextBee denied permission for this request. Please verify that your API key '
                'has SMS sending permissions and that the TextBee Android app has SEND_SMS permission.'
            ),
        )

    # 6. Generic provider rejection fallback
    return SMSResult(
        success=False,
        status_category='rejected',
        provider_status='rejected',
        user_message=(
            'TextBee rejected the SMS request. Please check the recipient phone '
            'number and your Android gateway device status.'
        ),
    )


def check_textbee_diagnostics() -> TextBeeDiagnosticResult:
    """
    Perform a safe, read-only diagnostic check against TextBee's official
    endpoints:
      - GET /api/v1/gateway/stats
      - GET /api/v1/gateway/devices
    Verifies API key authentication and confirms whether the configured
    TEXTBEE_DEVICE_ID belongs to the authenticated account and is enabled.
    Never sends an SMS and never exposes secrets.
    """
    api_key = _get_api_key()
    device_id = _get_device_id()

    if api_key.lower() in PLACEHOLDER_API_KEYS:
        return TextBeeDiagnosticResult(
            success=False,
            status_category='config_error',
            provider_status='missing_credentials',
            user_message=(
                'TextBee API Key is not configured. Please set TEXTBEE_API_KEY '
                'in your environment configuration.'
            ),
        )

    if device_id.lower() in PLACEHOLDER_DEVICE_IDS:
        return TextBeeDiagnosticResult(
            success=False,
            status_category='config_error',
            provider_status='missing_device_id',
            user_message=(
                'TextBee Device ID is not configured. Please set TEXTBEE_DEVICE_ID '
                'in your environment configuration.'
            ),
        )

    base_url = _get_base_url()
    stats_url = f'{base_url}/stats'
    devices_url = f'{base_url}/devices'
    timeout = _get_timeout_seconds()

    headers = {
        'x-api-key': api_key,
        'Accept': 'application/json',
    }

    try:
        stats_resp = requests.get(stats_url, headers=headers, timeout=timeout)
        devices_resp = requests.get(devices_url, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        return TextBeeDiagnosticResult(
            success=False,
            status_category='network_error',
            provider_status='timeout',
            user_message='The connection to TextBee timed out during diagnostics.',
        )
    except requests.exceptions.RequestException:
        return TextBeeDiagnosticResult(
            success=False,
            status_category='network_error',
            provider_status='connection_error',
            user_message='Unable to connect to TextBee during diagnostics.',
        )

    for resp in (stats_resp, devices_resp):
        if resp.status_code >= 400:
            try:
                err_body = resp.json() if resp.content else {}
            except ValueError:
                err_body = {}
            classified = _classify_textbee_error(resp.status_code, _extract_error_message(err_body))
            return TextBeeDiagnosticResult(
                success=False,
                status_category=classified.status_category,
                provider_status=classified.provider_status,
                user_message=classified.user_message,
                stats_status_code=stats_resp.status_code,
                devices_status_code=devices_resp.status_code,
            )

    try:
        stats_json = stats_resp.json() if stats_resp.content else {}
    except ValueError:
        stats_json = {}

    try:
        devices_json = devices_resp.json() if devices_resp.content else {}
    except ValueError:
        devices_json = {}

    stats_data: Dict[str, Any] = (
        stats_json.get('data')
        if isinstance(stats_json, dict) and isinstance(stats_json.get('data'), dict)
        else (stats_json if isinstance(stats_json, dict) else {})
    )
    total_sent_sms = stats_data.get('totalSentSMSCount')
    total_devices = stats_data.get('totalDeviceCount')

    devices_list: List[Dict[str, Any]] = []
    if isinstance(devices_json, list):
        devices_list = [d for d in devices_json if isinstance(d, dict)]
    elif isinstance(devices_json, dict):
        raw_list = devices_json.get('data')
        if isinstance(raw_list, list):
            devices_list = [d for d in raw_list if isinstance(d, dict)]

    if total_devices is None:
        total_devices = len(devices_list)

    matched_device: Optional[Dict[str, Any]] = None
    for dev in devices_list:
        candidate_id = str(dev.get('_id') or dev.get('id') or '').strip()
        if candidate_id == device_id:
            matched_device = dev
            break

    if matched_device is None:
        return TextBeeDiagnosticResult(
            success=False,
            status_category='invalid_device',
            provider_status='device_not_found',
            user_message=(
                'Authenticated with TextBee, but the configured TEXTBEE_DEVICE_ID '
                'was not found among the devices registered to this account.'
            ),
            stats_status_code=stats_resp.status_code,
            devices_status_code=devices_resp.status_code,
            total_devices=total_devices,
            total_sent_sms=total_sent_sms,
            device_found=False,
            device_enabled=False,
        )

    device_enabled = bool(matched_device.get('enabled', False))
    brand = str(matched_device.get('brand') or '').strip()
    model = str(matched_device.get('model') or matched_device.get('name') or '').strip()
    device_name = f'{brand} {model}'.strip() or 'Android Gateway Device'

    if not device_enabled:
        return TextBeeDiagnosticResult(
            success=False,
            status_category='device_unavailable',
            provider_status='device_offline_or_disabled',
            user_message=(
                f'Configured device ({device_name}) belongs to your TextBee account '
                'but is currently marked as disabled.'
            ),
            stats_status_code=stats_resp.status_code,
            devices_status_code=devices_resp.status_code,
            total_devices=total_devices,
            total_sent_sms=total_sent_sms,
            device_found=True,
            device_enabled=False,
            device_name=device_name,
        )

    return TextBeeDiagnosticResult(
        success=True,
        status_category='ok',
        provider_status='device_ready',
        user_message=(
            f'TextBee authentication succeeded and configured device ({device_name}) '
            'is registered and enabled.'
        ),
        stats_status_code=stats_resp.status_code,
        devices_status_code=devices_resp.status_code,
        total_devices=total_devices,
        total_sent_sms=total_sent_sms,
        device_found=True,
        device_enabled=True,
        device_name=device_name,
    )


def send_sms(recipient: str, message: str) -> SMSResult:
    """
    Submit an SMS message through the TextBee v1 REST API:
      POST https://api.textbee.dev/api/v1/gateway/send-sms

    Authenticates with the 'x-api-key' header, preserves international E.164
    recipient formatting with the leading '+', requires the configured
    TEXTBEE_DEVICE_ID, and distinguishes API queueing ('submitted'/'queued')
    from confirmed handset delivery ('delivered').
    """
    api_key = _get_api_key()
    device_id = _get_device_id()

    send_url = (
        getattr(settings, 'TEXTBEE_API_URL', TEXTBEE_DEFAULT_SEND_URL) or TEXTBEE_DEFAULT_SEND_URL
    ).strip()
    timeout = _get_timeout_seconds()

    # 1. Require configured API key
    if api_key.lower() in PLACEHOLDER_API_KEYS:
        return SMSResult(
            success=False,
            status_category='config_error',
            provider_status='missing_credentials',
            user_message=(
                'SMS service is not configured. Please set a valid TEXTBEE_API_KEY '
                'in your environment configuration.'
            ),
        )

    # 2. Require configured Device ID (never silently fall back to another device)
    if device_id.lower() in PLACEHOLDER_DEVICE_IDS:
        return SMSResult(
            success=False,
            status_category='config_error',
            provider_status='missing_device_id',
            user_message=(
                'TextBee Device ID is not configured. Please set TEXTBEE_DEVICE_ID '
                'in your environment configuration.'
            ),
        )

    formatted_recipient = format_textbee_recipient(recipient)

    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    payload = {
        'recipients': [formatted_recipient],
        'message': message,
        'deviceId': device_id,
    }

    try:
        response = requests.post(
            send_url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return SMSResult(
            success=False,
            status_category='network_error',
            provider_status='timeout',
            user_message=(
                'The connection to TextBee timed out while sending the request. '
                'Please check your internet connection and try again.'
            ),
        )
    except requests.exceptions.RequestException:
        return SMSResult(
            success=False,
            status_category='network_error',
            provider_status='connection_error',
            user_message=(
                'Unable to connect to TextBee due to a network error. '
                'Please verify your connection and try again later.'
            ),
        )

    try:
        body = response.json() if response.content else {}
    except ValueError:
        body = {}

    if not isinstance(body, dict):
        body = {}

    error_text = _extract_error_message(body)

    if response.status_code >= 400:
        return _classify_textbee_error(response.status_code, error_text)

    data = body.get('data') if isinstance(body.get('data'), dict) else body
    if not isinstance(data, dict):
        data = {}

    # Check if TextBee explicitly reported success: false inside a 200 payload
    explicit_success = data.get('success')
    if explicit_success is False or str(body.get('status', '')).strip().lower() == 'error':
        return _classify_textbee_error(response.status_code, error_text)

    sms_batch_id = (
        data.get('smsBatchId')
        or body.get('smsBatchId')
        or data.get('_id')
        or data.get('id')
    )
    message_id = str(sms_batch_id).strip() if sms_batch_id else None

    if explicit_success is not True and not message_id:
        return SMSResult(
            success=False,
            status_category='rejected',
            provider_status='unexpected_response',
            user_message=(
                'Received an unexpected response from the TextBee gateway. '
                'Submission status could not be verified.'
            ),
        )

    nested_status = str(data.get('status') or '').strip().lower()
    if nested_status == 'delivered':
        return SMSResult(
            success=True,
            status_category='delivered',
            provider_status='delivered',
            user_message=(
                f'SMS delivery to {formatted_recipient} was confirmed by TextBee (status: delivered).'
            ),
            recipient_formatted=formatted_recipient,
            message_id=message_id,
        )

    if nested_status in ('failed', 'undelivered', 'rejected'):
        return SMSResult(
            success=False,
            status_category='rejected',
            provider_status=nested_status,
            user_message=(
                f'TextBee reported that the SMS could not be delivered (status: {nested_status}).'
            ),
            recipient_formatted=formatted_recipient,
            message_id=message_id,
        )

    provider_status_label = nested_status or 'queued'
    return SMSResult(
        success=True,
        status_category='submitted',
        provider_status=provider_status_label,
        user_message=(
            f'SMS request accepted by TextBee and queued for your Android gateway device '
            f'to {formatted_recipient} (status: {provider_status_label}). '
            'Note: API acceptance confirms queueing only and does not guarantee '
            'final handset delivery.'
        ),
        recipient_formatted=formatted_recipient,
        message_id=message_id,
    )
