from unittest.mock import MagicMock, patch

import requests
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from sms_project.settings import parse_positive_int
from .forms import MAX_MESSAGE_LENGTH, SMSComposeForm
from .models import (
    SMSLog,
    build_message_excerpt,
    format_status_label,
    mask_phone_number,
)
from .services import (
    _get_timeout_seconds,
    check_textbee_diagnostics,
    format_textbee_recipient,
)
from .views import HISTORY_SAVE_WARNING_MESSAGE


@override_settings(
    TEXTBEE_API_KEY='test-textbee-key-998877',
    TEXTBEE_DEVICE_ID='665f1a2b3c4d5e6f7a8b9c0d',
    TEXTBEE_BASE_URL='https://api.textbee.dev/api/v1/gateway',
    TEXTBEE_API_URL='https://api.textbee.dev/api/v1/gateway/send-sms',
    TEXTBEE_TIMEOUT_SECONDS=5,
)
class SMSComposeTextBeeAndDashboardTests(TestCase):
    """Automated tests for Milestones 1–4 (Validation, TextBee API, SQLite History & Dashboard)."""

    def setUp(self):
        self.url = reverse('sms_app:index')

    # --- Milestone 1 & 2: Form Rendering, Validation & CSRF ---

    def test_homepage_renders_dashboard_form_counter_preview_and_empty_state(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sms_app/base.html')
        self.assertTemplateUsed(response, 'sms_app/index.html')
        self.assertContains(response, 'SMS Connect')
        self.assertContains(response, 'Messaging Workspace')
        self.assertContains(response, 'TextBee Gateway Configured')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'id="id_recipient"')
        self.assertContains(response, 'id="id_message"')
        self.assertContains(response, 'id="send-sms-btn"')
        self.assertContains(response, 'id="message-counter"')
        self.assertContains(response, 'id="message-preview"')
        self.assertContains(response, 'id="history-empty-state"')
        self.assertContains(response, 'No SMS attempts recorded yet')

    @patch('sms_app.services.requests.post')
    def test_empty_recipient_rejected_without_calling_provider_or_creating_log(self, mock_post):
        preserved_msg = 'This message should stay in the textarea.'
        response = self.client.post(
            self.url,
            data={'recipient': '', 'message': preserved_msg},
        )
        self.assertEqual(response.status_code, 200)
        mock_post.assert_not_called()
        self.assertEqual(SMSLog.objects.count(), 0)
        self.assertIsNone(response.context['sms_result'])
        self.assertContains(response, 'Please enter a recipient phone number.')
        self.assertContains(response, preserved_msg)

    @patch('sms_app.services.requests.post')
    def test_empty_or_whitespace_message_rejected_without_creating_log(self, mock_post):
        preserved_recipient = '+639171234567'
        for blank_msg in ['', '   \n\t  ']:
            with self.subTest(blank_msg=repr(blank_msg)):
                response = self.client.post(
                    self.url,
                    data={'recipient': preserved_recipient, 'message': blank_msg},
                )
                self.assertEqual(response.status_code, 200)
                mock_post.assert_not_called()
                self.assertEqual(SMSLog.objects.count(), 0)
                self.assertTrue(response.context['form'].errors.get('message'))
                self.assertContains(response, preserved_recipient)

    @patch('sms_app.services.requests.post')
    def test_invalid_phone_numbers_rejected_without_creating_log(self, mock_post):
        invalid_numbers = [
            '09171234567',
            '639171234567',
            '+6391712345',
            '+63917123456789',
            '+638171234567',
            '+63917ABCDEFG',
            '+0123456789',
        ]
        for bad_number in invalid_numbers:
            with self.subTest(bad_number=bad_number):
                response = self.client.post(
                    self.url,
                    data={
                        'recipient': bad_number,
                        'message': 'Test message for invalid phone',
                    },
                )
                self.assertEqual(response.status_code, 200)
                mock_post.assert_not_called()
                self.assertEqual(SMSLog.objects.count(), 0)
                self.assertTrue(response.context['form'].errors.get('recipient'))
                self.assertContains(response, bad_number)

    def test_message_at_exact_limit_accepted(self):
        exact_msg = 'A' * MAX_MESSAGE_LENGTH
        form = SMSComposeForm(data={'recipient': '+639171234567', 'message': exact_msg})
        self.assertTrue(form.is_valid())

    @patch('sms_app.services.requests.post')
    def test_message_exceeding_limit_rejected_without_creating_log(self, mock_post):
        over_limit_msg = 'B' * (MAX_MESSAGE_LENGTH + 1)
        response = self.client.post(
            self.url,
            data={'recipient': '+639171234567', 'message': over_limit_msg},
        )
        self.assertEqual(response.status_code, 200)
        mock_post.assert_not_called()
        self.assertEqual(SMSLog.objects.count(), 0)
        self.assertContains(
            response,
            f'Message cannot exceed {MAX_MESSAGE_LENGTH} characters',
        )
        self.assertContains(response, over_limit_msg)

    def test_csrf_protection_enforced(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            self.url,
            data={'recipient': '+639171234567', 'message': 'Testing CSRF enforcement'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SMSLog.objects.count(), 0)

    # --- Milestone 4: Model Helpers & Masking ---

    def test_smslog_model_creation_and_masking_helpers(self):
        self.assertEqual(mask_phone_number('+639171234567'), '+639*****4567')
        self.assertEqual(mask_phone_number('+14155552671'), '+141****2671')
        self.assertEqual(mask_phone_number('12345'), '***')

        long_msg = 'Line 1\nLine 2   with extra spaces and a very long body exceeding forty-eight characters easily.'
        excerpt = build_message_excerpt(long_msg, max_chars=48)
        self.assertTrue(excerpt.endswith('…'))
        self.assertLessEqual(len(excerpt), 49)
        self.assertNotIn('\n', excerpt)

        log = SMSLog.objects.create(
            recipient_masked=mask_phone_number('+639171234567'),
            message_excerpt=excerpt,
            sms_batch_id='batch_model_test',
            provider_status='dispatched',
            result_category=SMSLog.RESULT_SUBMITTED,
            error_category=None,
        )
        self.assertEqual(log.status_label, 'Dispatched')
        self.assertEqual(log.badge_variant, 'submitted')

    def test_user_friendly_status_labels_and_badge_variants(self):
        self.assertEqual(format_status_label('queued'), 'Queued')
        self.assertEqual(format_status_label('dispatched'), 'Dispatched')
        self.assertEqual(format_status_label('device_offline_or_disabled'), 'Device Unavailable')
        self.assertEqual(format_status_label('authentication_failed'), 'Authentication Failed')
        self.assertEqual(format_status_label('rejected'), 'Submission Failed')

        delivered_log = SMSLog(
            recipient_masked='+639*****4567',
            message_excerpt='Test',
            provider_status='delivered',
            result_category=SMSLog.RESULT_SUBMITTED,
        )
        self.assertEqual(delivered_log.badge_variant, 'delivered')

        queued_log = SMSLog(
            recipient_masked='+639*****4567',
            message_excerpt='Test',
            provider_status='queued',
            result_category=SMSLog.RESULT_SUBMITTED,
        )
        self.assertEqual(queued_log.badge_variant, 'submitted')

    # --- Milestone 3 & 4: TextBee Submission, History Creation & UI Reset ---

    def test_format_textbee_recipient_preserves_leading_plus(self):
        self.assertEqual(format_textbee_recipient('+639171234567'), '+639171234567')
        self.assertEqual(format_textbee_recipient('+14155552671'), '+14155552671')
        self.assertEqual(format_textbee_recipient('639171234567'), '+639171234567')
        self.assertEqual(format_textbee_recipient('09171234567'), '+639171234567')

    @patch('sms_app.services.requests.post')
    def test_successful_submission_creates_one_masked_log_and_clears_form_and_preview(
        self, mock_post
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data":{"success":true,"message":"SMS added to queue for processing","smsBatchId":"batch_tb_101","recipientCount":1}}'
        mock_resp.json.return_value = {
            'data': {
                'success': True,
                'message': 'SMS added to queue for processing',
                'smsBatchId': 'batch_tb_101',
                'recipientCount': 1,
            }
        }
        mock_post.return_value = mock_resp

        response = self.client.post(
            self.url,
            data={
                'recipient': '+639171234567',
                'message': 'Hello via TextBee Android Gateway!',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SMSLog.objects.count(), 1)

        log = SMSLog.objects.first()
        self.assertEqual(log.recipient_masked, '+639*****4567')
        self.assertEqual(log.message_excerpt, 'Hello via TextBee Android Gateway!')
        self.assertEqual(log.sms_batch_id, 'batch_tb_101')
        self.assertEqual(log.provider_status, 'queued')
        self.assertEqual(log.result_category, SMSLog.RESULT_SUBMITTED)
        self.assertIsNone(log.error_category)

        # Stats updated in context
        self.assertEqual(response.context['total_attempts'], 1)
        self.assertEqual(response.context['submitted_count'], 1)
        self.assertEqual(response.context['failed_count'], 0)

        # Both form and preview reset after successful submission
        self.assertIsNone(response.context['form']['recipient'].value())
        self.assertIsNone(response.context['form']['message'].value())
        self.assertContains(response, 'No recipient entered')
        self.assertContains(response, 'Your message preview will appear here as you type...')

        # Queued status is never falsely labeled as Delivered
        self.assertContains(response, 'Queued on TextBee Gateway')
        self.assertContains(response, 'does not guarantee final handset delivery')
        self.assertContains(response, '+639*****4567')
        self.assertNotContains(response, 'test-textbee-key-998877')

    @patch('sms_app.services.requests.post')
    def test_database_error_on_log_save_preserves_send_result_and_shows_warning_without_resending(
        self, mock_post
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data":{"success":true,"smsBatchId":"batch_db_err"}}'
        mock_resp.json.return_value = {
            'data': {'success': True, 'smsBatchId': 'batch_db_err'}
        }
        mock_post.return_value = mock_resp

        with patch('sms_app.views.SMSLog.objects.create', side_effect=DatabaseError('Disk I/O error')):
            response = self.client.post(
                self.url,
                data={
                    'recipient': '+639171234567',
                    'message': 'Testing DB failure isolation.',
                },
            )

        self.assertEqual(response.status_code, 200)
        # SMS was sent exactly once (never automatically resent on DB error)
        self.assertEqual(mock_post.call_count, 1)
        # Real SMS submission result is preserved
        self.assertTrue(response.context['sms_result'].success)
        self.assertContains(response, 'Queued on TextBee Gateway')
        self.assertContains(response, 'batch_db_err')
        # Separate history save warning banner is displayed
        self.assertEqual(response.context['history_save_warning'], HISTORY_SAVE_WARNING_MESSAGE)
        self.assertContains(response, 'History Save Warning')
        self.assertContains(response, HISTORY_SAVE_WARNING_MESSAGE)

    @override_settings(TEXTBEE_API_KEY='replace-with-textbee-api-key')
    @patch('sms_app.services.requests.post')
    def test_missing_api_key_logs_failed_attempt_and_preserves_draft(self, mock_post):
        draft_msg = 'Draft preserved when TextBee API key is missing.'
        response = self.client.post(
            self.url,
            data={'recipient': '+639171234567', 'message': draft_msg},
        )
        self.assertEqual(response.status_code, 200)
        mock_post.assert_not_called()
        self.assertEqual(SMSLog.objects.count(), 1)
        log = SMSLog.objects.first()
        self.assertEqual(log.result_category, SMSLog.RESULT_FAILED)
        self.assertEqual(log.error_category, 'config_error')
        self.assertEqual(log.provider_status, 'missing_credentials')
        self.assertContains(response, draft_msg)

    @override_settings(TEXTBEE_DEVICE_ID='')
    @patch('sms_app.services.requests.post')
    def test_missing_device_id_required_never_falls_back_to_default_device(self, mock_post):
        draft_msg = 'Draft preserved when TextBee Device ID is missing.'
        response = self.client.post(
            self.url,
            data={'recipient': '+639171234567', 'message': draft_msg},
        )
        self.assertEqual(response.status_code, 200)
        mock_post.assert_not_called()
        self.assertEqual(SMSLog.objects.count(), 1)
        log = SMSLog.objects.first()
        self.assertEqual(log.provider_status, 'missing_device_id')
        self.assertContains(response, draft_msg)

    @patch('sms_app.services.requests.post')
    def test_failed_provider_submissions_create_failed_logs_without_leaking_secrets(
        self, mock_post
    ):
        failure_cases = [
            (401, 'Invalid API key test-textbee-key-998877', 'auth_error', 'authentication_failed', 'Authentication Failed'),
            (404, 'Device not found', 'invalid_device', 'device_not_found', 'Device Not Found'),
            (400, 'Target device is offline or not connected', 'device_unavailable', 'device_offline_or_disabled', 'Device Unavailable'),
            (403, 'Forbidden resource: missing SEND_SMS permission', 'permission_error', 'permission_denied', 'Permission Denied'),
            (429, 'Daily quota exceeded', 'quota_error', 'quota_exceeded', 'Quota Exceeded'),
            (500, 'Internal stack trace secret_xyz', 'rejected', 'rejected', 'Submission Failed'),
        ]
        for idx, (status_code, raw_err, exp_err_cat, exp_status, exp_label) in enumerate(
            failure_cases, 1
        ):
            with self.subTest(status_code=status_code, exp_status=exp_status):
                mock_resp = MagicMock()
                mock_resp.status_code = status_code
                mock_resp.content = b'{"message":"error"}'
                mock_resp.json.return_value = {'message': raw_err}
                mock_post.return_value = mock_resp

                draft_msg = f'Draft #{idx} preserved on {exp_status}.'
                response = self.client.post(
                    self.url,
                    data={'recipient': '+639171234567', 'message': draft_msg},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, exp_label)
                self.assertContains(response, draft_msg)
                self.assertNotContains(response, 'test-textbee-key-998877')
                self.assertNotContains(response, 'Internal stack trace secret_xyz')

        self.assertEqual(SMSLog.objects.count(), len(failure_cases))
        self.assertEqual(
            SMSLog.objects.filter(result_category=SMSLog.RESULT_FAILED).count(),
            len(failure_cases),
        )
        for log in SMSLog.objects.all():
            self.assertEqual(log.recipient_masked, '+639*****4567')
            self.assertNotIn('917123', log.recipient_masked)
            self.assertIsNone(log.sms_batch_id)

    @patch('sms_app.services.requests.post')
    def test_network_timeout_and_connection_error_log_failed_attempt_and_preserve_draft(
        self, mock_post
    ):
        for exc, expected_status in [
            (requests.exceptions.Timeout('Request timed out'), 'timeout'),
            (requests.exceptions.ConnectionError('DNS failure'), 'connection_error'),
        ]:
            with self.subTest(expected_status=expected_status):
                mock_post.side_effect = exc
                draft_msg = f'Draft preserved during {expected_status}'
                response = self.client.post(
                    self.url,
                    data={'recipient': '+639171234567', 'message': draft_msg},
                )
                self.assertEqual(response.status_code, 200)
                sms_result = response.context['sms_result']
                self.assertFalse(sms_result.success)
                self.assertEqual(sms_result.status_category, 'network_error')
                self.assertEqual(sms_result.provider_status, expected_status)
                self.assertContains(response, draft_msg)

        self.assertEqual(SMSLog.objects.filter(error_category='network_error').count(), 2)

    @patch('sms_app.services.requests.post')
    def test_duplicate_submission_prevented_and_does_not_create_extra_log(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"data":{"success":true,"smsBatchId":"batch_dup_1"}}'
        mock_resp.json.return_value = {
            'data': {'success': True, 'smsBatchId': 'batch_dup_1'}
        }
        mock_post.return_value = mock_resp

        payload = {'recipient': '+639171234567', 'message': 'Duplicate check message'}
        first_resp = self.client.post(self.url, data=payload)
        self.assertEqual(first_resp.status_code, 200)
        self.assertEqual(SMSLog.objects.count(), 1)

        second_resp = self.client.post(self.url, data=payload)
        self.assertEqual(second_resp.status_code, 200)
        self.assertEqual(second_resp.context['sms_result'].status_category, 'duplicate')
        self.assertContains(second_resp, 'Duplicate submission prevented')
        # Still only 1 API call and 1 database record!
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(SMSLog.objects.count(), 1)

    def test_dashboard_statistics_and_newest_first_ordering_with_limit(self):
        # Create 12 records: 8 submitted (queued/dispatched) and 4 failed
        for i in range(1, 13):
            is_sub = i <= 8
            SMSLog.objects.create(
                recipient_masked=f'+639*****{1000 + i}',
                message_excerpt=f'Message attempt #{i}',
                sms_batch_id=f'batch_{i}' if is_sub else None,
                provider_status='dispatched' if is_sub else 'device_offline_or_disabled',
                result_category=SMSLog.RESULT_SUBMITTED if is_sub else SMSLog.RESULT_FAILED,
                error_category=None if is_sub else 'device_unavailable',
            )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_attempts'], 12)
        self.assertEqual(response.context['submitted_count'], 8)
        self.assertEqual(response.context['failed_count'], 4)

        recent_logs = response.context['recent_logs']
        self.assertEqual(len(recent_logs), 10)
        # Newest (#12) first, down to #3 (#1 and #2 excluded by the 10-item limit)
        self.assertEqual(recent_logs[0].message_excerpt, 'Message attempt #12')
        self.assertEqual(recent_logs[-1].message_excerpt, 'Message attempt #3')
        self.assertContains(response, 'Message attempt #12')
        self.assertNotContains(response, 'Message attempt #1<')

    # --- Safe Read-Only Diagnostics (GET /stats & GET /devices) ---

    @patch('sms_app.services.requests.get')
    def test_check_textbee_diagnostics_verifies_device_belongs_and_enabled(self, mock_get):
        stats_resp = MagicMock()
        stats_resp.status_code = 200
        stats_resp.content = b'{"data":{"totalSentSMSCount":12,"totalDeviceCount":1}}'
        stats_resp.json.return_value = {
            'data': {'totalSentSMSCount': 12, 'totalDeviceCount': 1, 'totalApiKeyCount': 1}
        }

        devices_resp = MagicMock()
        devices_resp.status_code = 200
        devices_resp.content = b'{"data":[{"_id":"665f1a2b3c4d5e6f7a8b9c0d","brand":"Samsung","model":"Galaxy A54","enabled":true}]}'
        devices_resp.json.return_value = {
            'data': [
                {
                    '_id': '665f1a2b3c4d5e6f7a8b9c0d',
                    'brand': 'Samsung',
                    'model': 'Galaxy A54',
                    'enabled': True,
                }
            ]
        }
        mock_get.side_effect = [stats_resp, devices_resp]

        diag = check_textbee_diagnostics()
        self.assertTrue(diag.success)
        self.assertEqual(diag.status_category, 'ok')
        self.assertEqual(diag.provider_status, 'device_ready')
        self.assertTrue(diag.device_found)
        self.assertTrue(diag.device_enabled)
        self.assertEqual(diag.device_name, 'Samsung Galaxy A54')

    @patch('sms_app.services.requests.get')
    def test_check_textbee_diagnostics_detects_missing_or_disabled_device(self, mock_get):
        stats_resp = MagicMock()
        stats_resp.status_code = 200
        stats_resp.content = b'{"data":{"totalDeviceCount":1}}'
        stats_resp.json.return_value = {'data': {'totalDeviceCount': 1}}

        other_dev_resp = MagicMock()
        other_dev_resp.status_code = 200
        other_dev_resp.content = b'{"data":[{"_id":"different_device_id","enabled":true}]}'
        other_dev_resp.json.return_value = {
            'data': [{'_id': 'different_device_id', 'enabled': True}]
        }
        mock_get.side_effect = [stats_resp, other_dev_resp]
        diag_missing = check_textbee_diagnostics()
        self.assertFalse(diag_missing.success)
        self.assertEqual(diag_missing.status_category, 'invalid_device')
        self.assertFalse(diag_missing.device_found)

        disabled_dev_resp = MagicMock()
        disabled_dev_resp.status_code = 200
        disabled_dev_resp.content = b'{"data":[{"_id":"665f1a2b3c4d5e6f7a8b9c0d","brand":"Pixel","model":"7","enabled":false}]}'
        disabled_dev_resp.json.return_value = {
            'data': [
                {
                    '_id': '665f1a2b3c4d5e6f7a8b9c0d',
                    'brand': 'Pixel',
                    'model': '7',
                    'enabled': False,
                }
            ]
        }
        mock_get.side_effect = [stats_resp, disabled_dev_resp]
        diag_disabled = check_textbee_diagnostics()
        self.assertFalse(diag_disabled.success)
        self.assertEqual(diag_disabled.status_category, 'device_unavailable')
        self.assertTrue(diag_disabled.device_found)
        self.assertFalse(diag_disabled.device_enabled)

    # --- Milestone 5: Audit Remediation Regression Tests ---

    def test_gateway_status_indicator_configured_vs_unconfigured(self):
        # Configured state (from class-level override_settings)
        configured_resp = self.client.get(self.url)
        self.assertEqual(configured_resp.status_code, 200)
        self.assertTrue(configured_resp.context['gateway_configured'])
        self.assertContains(configured_resp, 'TextBee Gateway Configured')
        self.assertNotContains(configured_resp, 'Gateway Setup Required')

        # Unconfigured API key
        with override_settings(TEXTBEE_API_KEY='replace-with-textbee-api-key'):
            unconf_key_resp = self.client.get(self.url)
            self.assertFalse(unconf_key_resp.context['gateway_configured'])
            self.assertContains(unconf_key_resp, 'Gateway Setup Required')
            self.assertNotContains(unconf_key_resp, 'TextBee Gateway Configured')

        # Unconfigured Device ID
        with override_settings(TEXTBEE_DEVICE_ID=''):
            unconf_dev_resp = self.client.get(self.url)
            self.assertFalse(unconf_dev_resp.context['gateway_configured'])
            self.assertContains(unconf_dev_resp, 'Gateway Setup Required')
            self.assertNotContains(unconf_dev_resp, 'TextBee Gateway Configured')

    def test_timeout_seconds_parsing_for_missing_blank_invalid_nonpositive_and_valid(self):
        cases = [
            (None, 10),
            ('', 10),
            ('   ', 10),
            ('abc', 10),
            ('0', 10),
            (0, 10),
            ('-5', 10),
            (-5, 10),
            ('15', 15),
            (15, 15),
        ]
        for raw_val, expected in cases:
            with self.subTest(raw_val=raw_val):
                self.assertEqual(parse_positive_int(raw_val, default=10), expected)
                with override_settings(TEXTBEE_TIMEOUT_SECONDS=raw_val):
                    self.assertEqual(_get_timeout_seconds(), expected)

    def test_form_accessibility_attributes_on_invalid_and_valid_fields(self):
        # Unbound form preserves default aria-describedby without aria-invalid
        unbound = SMSComposeForm()
        self.assertEqual(
            unbound.fields['recipient'].widget.attrs.get('aria-describedby'),
            'recipient-help',
        )
        self.assertNotIn('aria-invalid', unbound.fields['recipient'].widget.attrs)
        self.assertEqual(
            unbound.fields['message'].widget.attrs.get('aria-describedby'),
            'message-counter',
        )
        self.assertNotIn('aria-invalid', unbound.fields['message'].widget.attrs)

        # Invalid POST renders aria-invalid="true" and preserves existing aria-describedby + error IDs
        invalid_resp = self.client.post(
            self.url,
            data={'recipient': 'invalid-phone', 'message': ''},
        )
        self.assertEqual(invalid_resp.status_code, 200)
        self.assertContains(invalid_resp, 'aria-invalid="true"')
        self.assertContains(
            invalid_resp,
            'aria-describedby="recipient-help recipient-errors"',
        )
        self.assertContains(
            invalid_resp,
            'aria-describedby="message-counter message-errors"',
        )
        self.assertContains(invalid_resp, 'id="recipient-errors"')
        self.assertContains(invalid_resp, 'id="message-errors"')
