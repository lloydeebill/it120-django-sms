import re
from django import forms

MAX_MESSAGE_LENGTH = 160

E164_REGEX = re.compile(r'^\+[1-9]\d{7,14}$')
PH_E164_REGEX = re.compile(r'^\+639\d{9}$')


class SMSComposeForm(forms.Form):
    """Form for validating recipient phone number and SMS message body."""

    recipient = forms.CharField(
        label='Recipient Phone Number',
        required=True,
        strip=True,
        error_messages={
            'required': 'Please enter a recipient phone number.',
        },
        widget=forms.TextInput(
            attrs={
                'placeholder': '+639171234567',
                'autocomplete': 'tel',
                'class': 'form-input',
                'aria-describedby': 'recipient-help',
            }
        ),
    )

    message = forms.CharField(
        label='Message',
        required=True,
        strip=False,
        error_messages={
            'required': 'Please enter a message before sending.',
        },
        widget=forms.Textarea(
            attrs={
                'placeholder': 'Type your SMS message here...',
                'rows': 5,
                'class': 'form-textarea',
                'data-max-length': str(MAX_MESSAGE_LENGTH),
                'aria-describedby': 'message-counter',
            }
        ),
    )

    def clean_recipient(self):
        recipient = self.cleaned_data.get('recipient', '').strip()
        if not recipient:
            raise forms.ValidationError('Please enter a recipient phone number.')

        if not E164_REGEX.match(recipient):
            raise forms.ValidationError(
                'Enter a valid phone number in international E.164 format (e.g., +639171234567).'
            )

        if recipient.startswith('+63') and not PH_E164_REGEX.match(recipient):
            raise forms.ValidationError(
                'Philippine mobile numbers must follow +639XXXXXXXXX format (10 digits after +63).'
            )

        return recipient

    def clean_message(self):
        message = self.cleaned_data.get('message', '')
        if not message or not message.strip():
            raise forms.ValidationError('Please enter a non-empty message before sending.')

        if len(message) > MAX_MESSAGE_LENGTH:
            raise forms.ValidationError(
                f'Message cannot exceed {MAX_MESSAGE_LENGTH} characters (currently {len(message)} characters).'
            )

        return message

    def full_clean(self):
        super().full_clean()
        if not self.is_bound:
            return

        if 'recipient' in self._errors:
            self.fields['recipient'].widget.attrs['aria-invalid'] = 'true'
            self.fields['recipient'].widget.attrs['aria-describedby'] = (
                'recipient-help recipient-errors'
            )

        if 'message' in self._errors:
            self.fields['message'].widget.attrs['aria-invalid'] = 'true'
            self.fields['message'].widget.attrs['aria-describedby'] = (
                'message-counter message-errors'
            )
