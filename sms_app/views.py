import hashlib
import time
from typing import Optional

from django.db import DatabaseError
from django.shortcuts import render

from .forms import MAX_MESSAGE_LENGTH, SMSComposeForm
from .models import SMSLog, build_message_excerpt, mask_phone_number
from .services import SMSResult, is_textbee_configured, send_sms

DUPLICATE_SUBMISSION_WINDOW_SECONDS = 10
RECENT_HISTORY_LIMIT = 10

HISTORY_SAVE_WARNING_MESSAGE = (
    'The SMS request was processed, but the attempt could not be saved to local '
    'message history due to a database error.'
)


def _compute_submission_fingerprint(recipient: str, message: str) -> str:
    payload = f'{recipient.strip()}::{message}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _is_duplicate_submission(request, fingerprint: str) -> bool:
    last_sub = request.session.get('last_sms_submission')
    if not isinstance(last_sub, dict):
        return False

    prev_fp = last_sub.get('fingerprint')
    prev_ts = last_sub.get('timestamp', 0.0)
    try:
        elapsed = time.time() - float(prev_ts)
    except (TypeError, ValueError):
        return False

    return prev_fp == fingerprint and 0 <= elapsed < DUPLICATE_SUBMISSION_WINDOW_SECONDS


def _record_successful_submission(request, fingerprint: str) -> None:
    request.session['last_sms_submission'] = {
        'fingerprint': fingerprint,
        'timestamp': time.time(),
    }


def _record_sms_log(recipient: str, message: str, sms_result: SMSResult) -> Optional[str]:
    """
    Persist a privacy-safe SMSLog entry in SQLite after a sending attempt.
    Returns a user-facing warning message if a DatabaseError occurs, without
    raising or re-triggering any SMS request.
    """
    result_category = (
        SMSLog.RESULT_SUBMITTED if sms_result.success else SMSLog.RESULT_FAILED
    )
    error_category = None if sms_result.success else sms_result.status_category

    try:
        SMSLog.objects.create(
            recipient_masked=mask_phone_number(recipient),
            message_excerpt=build_message_excerpt(message),
            sms_batch_id=sms_result.message_id if sms_result.success else None,
            provider_status=sms_result.provider_status,
            result_category=result_category,
            error_category=error_category,
        )
        return None
    except DatabaseError:
        return HISTORY_SAVE_WARNING_MESSAGE


def index(request):
    """Display, validate, and submit the SMS composition form and render dashboard metrics."""
    sms_result = None
    history_save_warning = None

    if request.method == 'POST':
        form = SMSComposeForm(request.POST)
        if form.is_valid():
            recipient = form.cleaned_data['recipient']
            message = form.cleaned_data['message']
            fingerprint = _compute_submission_fingerprint(recipient, message)

            if _is_duplicate_submission(request, fingerprint):
                sms_result = SMSResult(
                    success=False,
                    status_category='duplicate',
                    provider_status='duplicate_blocked',
                    user_message=(
                        'Duplicate submission prevented: This exact message was just '
                        'submitted to this recipient. Please wait a few seconds before '
                        'sending again.'
                    ),
                )
            else:
                sms_result = send_sms(recipient=recipient, message=message)
                history_save_warning = _record_sms_log(recipient, message, sms_result)
                if sms_result.success:
                    _record_successful_submission(request, fingerprint)
                    # Clear both the compose form and the live message preview
                    form = SMSComposeForm()
    else:
        form = SMSComposeForm()

    try:
        total_attempts = SMSLog.objects.count()
        submitted_count = SMSLog.objects.filter(
            result_category=SMSLog.RESULT_SUBMITTED
        ).count()
        failed_count = SMSLog.objects.filter(
            result_category=SMSLog.RESULT_FAILED
        ).count()
        recent_logs = list(SMSLog.objects.all()[:RECENT_HISTORY_LIMIT])
    except DatabaseError:
        total_attempts = 0
        submitted_count = 0
        failed_count = 0
        recent_logs = []

    context = {
        'form': form,
        'max_message_length': MAX_MESSAGE_LENGTH,
        'sms_result': sms_result,
        'history_save_warning': history_save_warning,
        'gateway_configured': is_textbee_configured(),
        'total_attempts': total_attempts,
        'submitted_count': submitted_count,
        'failed_count': failed_count,
        'recent_logs': recent_logs,
    }
    return render(request, 'sms_app/index.html', context)
