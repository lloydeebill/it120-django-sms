from django.contrib import admin

from .models import SMSLog


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = (
        'recipient_masked',
        'message_excerpt',
        'provider_status',
        'result_category',
        'sms_batch_id',
        'created_at',
    )
    list_filter = ('result_category', 'provider_status')
    readonly_fields = (
        'recipient_masked',
        'message_excerpt',
        'sms_batch_id',
        'provider_status',
        'result_category',
        'error_category',
        'created_at',
    )
