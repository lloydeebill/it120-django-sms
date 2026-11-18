(function () {
    'use strict';

    const formEl = document.getElementById('sms-compose-form');
    const submitBtn = document.getElementById('send-sms-btn');
    const recipientInput = document.getElementById('id_recipient');
    const messageInput = document.getElementById('id_message');
    const counterBadge = document.getElementById('message-counter');
    const currentCountEl = document.getElementById('char-count-current');
    const maxCountEl = document.getElementById('char-count-max');
    const previewRecipientEl = document.getElementById('preview-recipient');
    const previewMessageEl = document.getElementById('preview-message');
    const previewCharStatusEl = document.getElementById('preview-char-status');

    if (!recipientInput || !messageInput) {
        return;
    }

    const maxLength = parseInt(messageInput.getAttribute('data-max-length') || '160', 10);
    const warningThreshold = Math.floor(maxLength * 0.85);

    function updatePreviewAndCounter(shouldUpdatePreviewText) {
        const recipientVal = recipientInput.value.trim();
        const messageVal = messageInput.value;
        const length = messageVal.length;

        if (currentCountEl) {
            currentCountEl.textContent = String(length);
        }
        if (maxCountEl) {
            maxCountEl.textContent = String(maxLength);
        }

        if (counterBadge) {
            counterBadge.classList.remove('is-warning', 'is-over-limit');
            if (length > maxLength) {
                counterBadge.classList.add('is-over-limit');
            } else if (length >= warningThreshold) {
                counterBadge.classList.add('is-warning');
            }
        }

        if (shouldUpdatePreviewText) {
            if (previewRecipientEl) {
                previewRecipientEl.textContent = recipientVal || 'No recipient entered';
            }

            if (previewMessageEl) {
                if (messageVal.trim().length > 0) {
                    previewMessageEl.textContent = messageVal;
                    previewMessageEl.classList.remove('is-placeholder');
                } else {
                    previewMessageEl.textContent = 'Your message preview will appear here as you type...';
                    previewMessageEl.classList.add('is-placeholder');
                }
            }
        }

        if (previewCharStatusEl) {
            const remaining = maxLength - length;
            if (remaining >= 0) {
                previewCharStatusEl.textContent = length + ' of ' + maxLength + ' characters used (' + remaining + ' remaining)';
            } else {
                previewCharStatusEl.textContent = length + ' of ' + maxLength + ' characters used (' + Math.abs(remaining) + ' over limit)';
            }
        }
    }

    recipientInput.addEventListener('input', function () {
        updatePreviewAndCounter(true);
    });
    messageInput.addEventListener('input', function () {
        updatePreviewAndCounter(true);
    });

    if (formEl && submitBtn) {
        formEl.addEventListener('submit', function () {
            if (submitBtn.disabled) {
                return;
            }
            submitBtn.disabled = true;
            submitBtn.textContent = 'Sending SMS...';
        });
    }

    // Initialize counter on load; only overwrite server-rendered preview if fields have input
    const hasInitialInput = recipientInput.value.trim().length > 0 || messageInput.value.length > 0;
    updatePreviewAndCounter(hasInitialInput);
})();
