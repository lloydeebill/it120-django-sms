from django.db import models

STATUS_LABELS = {
    'queued': 'Queued',
    'dispatched': 'Dispatched',
    'accepted': 'Accepted',
    'submitted': 'Submitted',
    'delivered': 'Delivered',
    'authentication_failed': 'Authentication Failed',
    'device_not_found': 'Device Not Found',
    'device_offline_or_disabled': 'Device Unavailable',
    'permission_denied': 'Permission Denied',
    'quota_exceeded': 'Quota Exceeded',
    'timeout': 'Request Timed Out',
    'connection_error': 'Connection Error',
    'missing_credentials': 'Credentials Missing',
    'missing_device_id': 'Device ID Missing',
    'rejected': 'Submission Failed',
    'unexpected_response': 'Submission Failed',
    'duplicate_blocked': 'Duplicate Blocked',
}


def format_status_label(provider_status: str) -> str:
    """Return a clean, user-friendly UI label for a technical provider_status slug."""
    key = (provider_status or '').strip().lower()
    if key in STATUS_LABELS:
        return STATUS_LABELS[key]
    if not key:
        return 'Unknown'
    return key.replace('_', ' ').title()


def mask_phone_number(phone: str) -> str:
    """
    Mask a phone number for privacy in SQLite storage and dashboard display
    (e.g., '+639171234567' -> '+639*****4567').
    """
    cleaned = (phone or '').strip()
    if len(cleaned) <= 7:
        return '***'
    prefix = cleaned[:4]
    suffix = cleaned[-4:]
    masked_middle_len = max(len(cleaned) - 8, 3)
    return f'{prefix}{"*" * masked_middle_len}{suffix}'


def build_message_excerpt(message: str, max_chars: int = 48) -> str:
    """
    Collapse whitespace/newlines and return a short message excerpt so full
    SMS bodies do not need to be retained in SQLite.
    """
    normalized = ' '.join((message or '').split())
    if len(normalized) <= max_chars:
        return normalized
    return f'{normalized[:max_chars].rstrip()}…'


class SMSLog(models.Model):
    """
    Lightweight SQLite record of a validated SMS sending attempt.
    Stores only masked recipient phone numbers, short message excerpts,
    and safe technical status/error categories (never credentials or raw errors).
    """

    RESULT_SUBMITTED = 'submitted'
    RESULT_FAILED = 'failed'
    RESULT_CHOICES = [
        (RESULT_SUBMITTED, 'Submitted'),
        (RESULT_FAILED, 'Failed'),
    ]

    recipient_masked = models.CharField(
        max_length=24,
        help_text='Masked E.164 recipient phone number (e.g., +639*****4567).',
    )
    message_excerpt = models.CharField(
        max_length=64,
        help_text='Short excerpt of the SMS message body.',
    )
    sms_batch_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text='TextBee smsBatchId reference when accepted by the gateway.',
    )
    provider_status = models.CharField(
        max_length=32,
        help_text='Technical provider status slug (e.g., queued, dispatched, authentication_failed).',
    )
    result_category = models.CharField(
        max_length=16,
        choices=RESULT_CHOICES,
        db_index=True,
        help_text='High-level outcome category (submitted or failed) for dashboard statistics.',
    )
    error_category = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text='Safe error category when result_category is failed; null on success.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='Timezone-aware timestamp of the sending attempt.',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'SMS Attempt Log'
        verbose_name_plural = 'SMS Attempt Logs'

    def __str__(self) -> str:
        return f'{self.recipient_masked} [{self.provider_status}] @ {self.created_at:%Y-%m-%d %H:%M}'

    @property
    def status_label(self) -> str:
        """Human-friendly status label for dashboard rendering."""
        return format_status_label(self.provider_status)

    @property
    def badge_variant(self) -> str:
        """
        Return semantic badge style ('delivered', 'submitted', or 'failed').
        Only explicitly verified 'delivered' status uses the green 'delivered' badge.
        """
        if self.provider_status == 'delivered':
            return 'delivered'
        if self.result_category == self.RESULT_SUBMITTED:
            return 'submitted'
        return 'failed'
