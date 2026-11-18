# SMS Connect — Django SMS Gateway Application

**Course:** IT 120 – Integrative Programming and Technologies
**Assignment:** Group Laboratory / Assignment — Build a Django Application for Sending SMS

---

## 1. Project Overview & Objectives

**SMS Connect** is a web application built with Python and the Django 5.2 framework that enables users to compose, validate, dispatch, and monitor outbound SMS messages to Philippine (`+639XXXXXXXXX`) and international E.164 mobile numbers through the **TextBee v1 Android SMS Gateway REST API** (`https://api.textbee.dev/api/v1/gateway/send-sms`).

### Learning & System Objectives
1. **Functional Django Web Application**: Provide a clean, server-rendered messaging workspace with an accessible SMS composition form, live character counter, real-time handset preview, and SQLite attempt history dashboard.
2. **External SMS API Integration**: Communicate with TextBee's REST API via an isolated service module (`sms_app/services.py`) using `x-api-key` authentication and a paired Android gateway device.
3. **Strict Validation & Error Handling**: Enforce server-side E.164 phone number and message length validation (`160` characters max) and gracefully classify authentication failures, missing/offline devices, permission errors, quota limits, and network timeouts without exposing secrets.
4. **Honest Delivery Status Reporting**: Distinguish between API submission/queueing (`Queued` / `Dispatched`) and verified handset delivery (`Delivered`).
5. **Security & Privacy by Design**: Load all secrets from environment variables (`.env`), enforce Django CSRF protection, prevent accidental duplicate submissions, and store only masked phone numbers (`+639*****4567`) and short 48-character message excerpts in SQLite (`SMSLog`).

---

## 2. Group Members & Assigned Responsibilities

| Rank | Group Member | Role & Assigned Responsibilities | Verification Status |
| :--- | :--- | :--- | :--- |
| **1 (Lead / High)** | **Lloyd Bill Lariosa** | **Project Lead & Backend/Integration Architect** — Django project setup (`sms_project`, `sms_app`), URL routing, core view logic, TextBee REST API service (`sms_app/services.py`), Android gateway setup & FCM troubleshooting, `SMSLog` database model/migrations, and environment security. | Implementation & live Android gateway verification completed; final GitHub commit attribution to be confirmed by group before submission. |
| **2 (Medium)** | **Ivy Tabada** | **UI/UX, Forms & Validation Developer** — Modern messaging workspace layout (`base.html`, `index.html`, `styles.css`), responsive desktop/mobile design, `SMSComposeForm` E.164 & message validation (`forms.py`), accessibility attributes (`aria-invalid`, `aria-describedby`), live character counter, and live message preview (`app.js`). | Implementation & UI verification completed; final GitHub commit & video segment attribution to be confirmed by group before submission. |
| **3 (Support)** | **Junalea Mhae Gallogo** | **QA, Testing & Documentation Specialist** — Automated test suite verification (`tests.py`), test case documentation and results reporting, setup/configuration documentation (`README.md`), and demonstration video preparation. | Automated test suite & documentation completed; demonstration video recording to be confirmed by group before submission. |

---

## 3. Main Features

- **SMS Composition Form**: Server-rendered Django form protected by CSRF middleware with recipient phone number input, message textarea, and a double-submit-protected **Send SMS** button.
- **Server-Side Input Validation**:
  - Accepts valid international E.164 phone numbers (`^\+[1-9]\d{7,14}$`) and enforces the 10-digit subscriber format for Philippine mobile numbers (`+639XXXXXXXXX`).
  - Rejects empty inputs, whitespace-only messages, and messages exceeding `160` characters.
  - Preserves user drafts whenever validation or provider submission fails, and attaches accessible `aria-invalid="true"` and `aria-describedby` attributes to invalid fields.
- **Live Character Counter & Real-Time Message Preview**:
  - Displays current character usage (`0 / 160 characters`) with visual warning (`>= 136` chars) and over-limit (`> 160` chars) states.
  - Updates a phone-inspired message bubble preview in real time as the user types, and resets both the form and preview cleanly after a successful submission.
- **Duplicate Submission Guard**:
  - Combines client-side submit button locking (`Sending SMS...`) with a 10-second server-side session SHA-256 fingerprint cooldown to block accidental double-clicks or page refreshes.
- **SQLite Attempt History & Summary Dashboard (`SMSLog`)**:
  - Displays live SQLite counters for **Total Attempts**, **Submitted** (accepted/queued/dispatched by TextBee), and **Failed** (rejected or unsuccessful attempts).
  - Renders the latest 10 attempts (newest first) in the **Recent Messages** table with masked recipient numbers (`+639*****4567`), 48-character message excerpts, readable status pills, TextBee `smsBatchId`, and `Asia/Manila` (`PHT`) timestamps.
  - Isolates SQLite history writes so a database failure never triggers an automatic SMS resend and displays a separate **History Save Warning** banner while preserving the real SMS sending result.

---

## 4. SMS Sending Workflow

1. **Open Workspace (`GET /`)**: The user opens the **SMS Connect** dashboard, which displays the gateway configuration status (`TextBee Gateway Configured` or `Gateway Setup Required`), current SQLite summary statistics, the composition form, live preview, and recent message history.
2. **Compose & Preview**: The user enters a recipient phone number in E.164 format (e.g., `+639171234567`) and composes a message (up to `160` characters) while the live character counter and handset preview update dynamically.
3. **Validate (`SMSComposeForm`)**: On `POST /`, Django verifies the CSRF token and validates the recipient format and message length on the server. Invalid inputs return field-level errors without calling TextBee or creating a history record.
4. **Deduplicate**: The view checks whether an identical `(recipient, message)` fingerprint was submitted within the last 10 seconds. Duplicate requests are blocked with an amber warning.
5. **Dispatch via TextBee (`services.send_sms`)**: Valid requests are sent via `POST https://api.textbee.dev/api/v1/gateway/send-sms` with header `x-api-key` and JSON payload `{"recipients": ["+639..."], "message": "...", "deviceId": "..."}`.
6. **Record History & Display Feedback**: The attempt outcome is saved in `SMSLog` (with masked phone number and short excerpt), dashboard counters update, and a clear banner reports whether the message was queued on TextBee (`smsBatchId`) or failed (preserving the user's draft on failure).

---

## 5. Technology Stack & Dependencies

- **Backend**: Python 3.11+, Django `5.2.19`
- **Database**: SQLite 3 (via Django ORM)
- **HTTP Client & Config**: `requests==2.34.2`, `python-dotenv==1.2.4`
- **Frontend**: Django Templates, semantic HTML5, modern responsive CSS3 (`styles.css`), vanilla JavaScript (`app.js`)
- **SMS Gateway**: TextBee v1 REST API (`https://api.textbee.dev/api/v1/gateway`) paired with an Android gateway phone

All pinned Python dependencies are listed in `requirements.txt`.

---

## 6. Project Structure

```text
django-sms/
├── .env.example                 # Safe template for local environment variables
├── .gitignore                   # Excludes .env, .venv/, __pycache__/, and *.sqlite3
├── manage.py                    # Django management entry point
├── README.md                    # Complete project documentation and test report
├── requirements.txt             # Pinned Python package dependencies
├── sms_project/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py              # Environment loading, secret handling, Asia/Manila timezone
│   ├── urls.py                  # Root URL routing
│   └── wsgi.py
└── sms_app/
    ├── __init__.py
    ├── admin.py                 # Read-only SMSLog registration for Django admin
    ├── apps.py
    ├── forms.py                 # SMSComposeForm (E.164 & 160-char validation + ARIA)
    ├── models.py                # SMSLog model, phone masking, and excerpt helpers
    ├── services.py              # TextBee REST API integration & read-only diagnostics
    ├── tests.py                 # 23 mocked unit, view, accessibility, and database tests
    ├── urls.py                  # App URL routing
    ├── views.py                 # Dashboard view, duplicate guard, and DB error isolation
    ├── migrations/
    │   ├── __init__.py
    │   └── 0001_initial.py      # Initial migration for SMSLog
    ├── static/sms_app/
    │   ├── app.js               # Live character counter, preview, and submit button lock
    │   └── styles.css           # Responsive dashboard and mobile table styling
    └── templates/sms_app/
        ├── base.html            # Base layout, header indicator, and footer
        └── index.html           # Summary cards, compose/preview workspace, and history table
```

---

## 7. Installation & Setup Instructions

Open a terminal in the `django-sms/` directory:

```powershell
# 1. Create a Python virtual environment
python -m venv .venv

# 2. Activate the virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 3. Install required dependencies
pip install -r requirements.txt

# 4. Copy the example environment configuration
Copy-Item .env.example .env
```

---

## 8. TextBee Account & Android Device Configuration

1. **Create a TextBee Account & Pair Your Android Phone**:
   - Sign in at `https://textbee.dev` and install the official **TextBee** Android app on your Android phone with an active SIM card.
   - Generate an **API Key** on the TextBee dashboard and scan the QR code (or enter the key) in the Android app to register the device.
   - Copy your **API Key** (`TEXTBEE_API_KEY`) and the registered phone's **Device ID** (`TEXTBEE_DEVICE_ID`) into your local `django-sms/.env` file.
2. **Required Android App & Power Settings**:
   - Grant TextBee permissions for **Send SMS**, **Receive SMS**, **Read Phone State**, and **Post Notifications**.
   - Enable **Sticky Notification** inside the TextBee Android app so the gateway service stays active in the foreground.
   - Disable system **Battery Saver** and set TextBee's battery usage to **No restrictions / Unrestricted**.
3. **Note on Xiaomi China ROM (`CNXM`) Devices**:
   - TextBee relies on **Firebase Cloud Messaging (FCM)** (`com.google.android.gms`) to push queued SMS jobs from the cloud to the phone (`dispatched` → `pushReceivedAt`).
   - During our testing, an initial Xiaomi Redmi phone running a China ROM (`OS3.0.308.0.WOKCNXM`) accepted outbound heartbeats but blocked incoming FCM pushes (`status: dispatched` with `pushReceivedAt` remaining empty). Switching to a standard Android phone with normal Google Play Services / FCM support resolved the issue immediately. If using a China ROM device, we recommend switching to a standard Global-ROM Android device.

---

## 9. Environment Variables (`.env`)

Configure the following variables in `django-sms/.env` (never commit `.env` to Git):

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | Yes (in prod) | Ephemeral dev key when `DEBUG=True` | Secret key for cryptographic signing. Required if `DJANGO_DEBUG=False`. |
| `DJANGO_DEBUG` | No | `True` | Set to `True` for local development; `False` in production. |
| `TEXTBEE_API_KEY` | Yes | None | TextBee API key sent via the `x-api-key` HTTP header. |
| `TEXTBEE_DEVICE_ID` | Yes | None | Target Android gateway `deviceId` registered on your TextBee account. |
| `TEXTBEE_BASE_URL` | No | `https://api.textbee.dev/api/v1/gateway` | Base URL for TextBee gateway endpoints. |
| `TEXTBEE_TIMEOUT_SECONDS` | No | `10` | Positive integer HTTP timeout in seconds (falls back to `10` if blank/invalid). |

> **Important:** `settings.py` loads `.env` once at startup via `load_dotenv(BASE_DIR / '.env')`. **Restart `python manage.py runserver` whenever you edit `.env`** so updated credentials take effect.

---

## 10. Running Migrations, the Server & Automated Tests

From the `django-sms/` directory:

```powershell
# Apply SQLite database migrations
.\.venv\Scripts\python.exe manage.py migrate

# Verify project configuration and migration consistency
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run

# Run the complete automated test suite (23 mocked tests — never sends real SMS)
.\.venv\Scripts\python.exe manage.py test sms_app -v 2

# Start the local development server at http://127.0.0.1:8000/
.\.venv\Scripts\python.exe manage.py runserver
```

---

## 11. Real SMS Testing Instructions

1. Confirm `TEXTBEE_API_KEY` and `TEXTBEE_DEVICE_ID` are set in `django-sms/.env` and your paired Android phone is online with its SIM card in service.
2. Start the server (`python manage.py runserver`) and open `http://127.0.0.1:8000/`.
3. Verify the top-right header badge reads **`TextBee Gateway Configured`**.
4. Enter an **authorized test recipient** in E.164 format (e.g., `+639XXXXXXXXX`), enter a short test message, and click **Send SMS**.
5. Confirm that:
   - The **Queued on TextBee Gateway** banner appears with a `Batch ID (smsBatchId)`.
   - The attempt is added to **Recent Messages** with a masked phone number (`+639*****XXXX`) and `Queued` status badge, and **Submitted** increments by `1`.
   - The authorized test recipient receives the physical SMS on their handset.

---

## 12. Testing Report & Verification Results

### A. Automated Test Suite Results (`python manage.py test sms_app -v 2`)
All **23 automated tests** use `unittest.mock.patch` to mock external HTTP calls so unit tests never send real SMS messages or consume carrier credits.

| # | Test Case / Method | Scenario & Input | Expected Result | Actual Result | Outcome |
| :- | :--- | :--- | :--- | :--- | :--- |
| 1 | `test_homepage_renders_dashboard_form_counter_preview_and_empty_state` | `GET /` on empty database | Renders header, 3 stat cards (`0`), compose form, CSRF token, counter, preview, and empty history state | Rendered HTTP `200` with all dashboard sections and empty state | **PASS** |
| 2 | `test_empty_recipient_rejected_without_calling_provider_or_creating_log` | `POST /` with blank `recipient` | Rejects submission, shows field error, preserves message draft, `0` API calls, `0` DB logs | Rejected with field error, draft preserved, `0` API calls, `0` DB logs | **PASS** |
| 3 | `test_empty_or_whitespace_message_rejected_without_creating_log` | `POST /` with `""` and `"   \n\t  "` | Rejects blank/whitespace message, preserves recipient, `0` API calls, `0` DB logs | Rejected both sub-cases, recipient preserved, `0` API calls, `0` DB logs | **PASS** |
| 4 | `test_invalid_phone_numbers_rejected_without_creating_log` | `POST /` with 7 invalid phone formats (`0917...`, `639...`, too short/long, letters) | Rejects all 7 formats with E.164 field error, preserves inputs, `0` API calls, `0` DB logs | All 7 invalid phone formats rejected without calling provider | **PASS** |
| 5 | `test_message_at_exact_limit_accepted` | `SMSComposeForm` with `160`-char message | Form validation succeeds (`is_valid() == True`) | `form.is_valid()` returned `True` | **PASS** |
| 6 | `test_message_exceeding_limit_rejected_without_creating_log` | `POST /` with `161`-char message | Rejects with max-length error, preserves input, `0` API calls, `0` DB logs | Rejected with `160`-char limit error and preserved draft | **PASS** |
| 7 | `test_csrf_protection_enforced` | `POST /` without CSRF token (`enforce_csrf_checks=True`) | Rejects request with HTTP `403 Forbidden` and creates `0` DB logs | Returned HTTP `403 Forbidden`, `0` DB logs | **PASS** |
| 8 | `test_smslog_model_creation_and_masking_helpers` | `mask_phone_number` & `build_message_excerpt` | Masks `+639171234567` → `+639*****4567` and truncates long excerpts to 48 chars + `…` | Masked phone and truncated excerpt verified on `SMSLog` | **PASS** |
| 9 | `test_user_friendly_status_labels_and_badge_variants` | Status mapping (`queued`, `dispatched`, `delivered`, `device_offline_or_disabled`) | Maps technical slugs to readable UI labels; only `delivered` gets green `delivered` badge | Labels and badge variants matched specification | **PASS** |
| 10 | `test_format_textbee_recipient_preserves_leading_plus` | `format_textbee_recipient` with `+639...`, `+1415...`, `639...`, `09...` | Preserves/normalizes international E.164 with leading `+` | Returned `+639171234567` and `+14155552671` | **PASS** |
| 11 | `test_successful_submission_creates_one_masked_log_and_clears_form_and_preview` | Mocked `200 OK` (`smsBatchId: batch_tb_101`) | Calls TextBee once, creates 1 `SMSLog` (`queued`, masked phone), updates stats, resets form & preview, does not claim delivery | Created 1 masked `SMSLog`, updated stats (`1` Submitted), cleared form & preview | **PASS** |
| 12 | `test_database_error_on_log_save_preserves_send_result_and_shows_warning_without_resending` | Mocked `200 OK` + simulated `DatabaseError` on `SMSLog.objects.create` | Preserves `Queued` SMS result, displays `History Save Warning` banner, never resends SMS | Preserved send result, showed warning banner, `mock_post.call_count == 1` | **PASS** |
| 13 | `test_missing_api_key_logs_failed_attempt_and_preserves_draft` | Placeholder `TEXTBEE_API_KEY` | Skips HTTP call, logs `missing_credentials` failure, preserves message draft | Logged 1 failed attempt, preserved draft, `0` HTTP calls | **PASS** |
| 14 | `test_missing_device_id_required_never_falls_back_to_default_device` | Empty `TEXTBEE_DEVICE_ID` | Skips HTTP call, logs `missing_device_id` failure, never falls back to default device | Logged 1 failed attempt, preserved draft, `0` HTTP calls | **PASS** |
| 15 | `test_failed_provider_submissions_create_failed_logs_without_leaking_secrets` | Mocked `401`, `404`, `400` (offline), `403`, `429`, and `500` responses | Classifies each error accurately, logs 6 failed records with masked phone, preserves drafts, hides API key & raw errors | All 6 error categories classified & logged safely without leaking secrets | **PASS** |
| 16 | `test_network_timeout_and_connection_error_log_failed_attempt_and_preserve_draft` | Mocked `Timeout` and `ConnectionError` exceptions | Catches exceptions, logs `timeout` / `connection_error`, preserves draft (`HTTP 200`) | Both network exceptions handled gracefully and logged | **PASS** |
| 17 | `test_duplicate_submission_prevented_and_does_not_create_extra_log` | Two identical `POST /` requests within 10s window | First request sends & logs; second is blocked as `duplicate_blocked` with no extra API call or DB log | `mock_post.call_count == 1` and `SMSLog.objects.count() == 1` | **PASS** |
| 18 | `test_dashboard_statistics_and_newest_first_ordering_with_limit` | 12 `SMSLog` rows (`8` submitted, `4` failed) | Stats show `Total: 12`, `Submitted: 8`, `Failed: 4`; table shows newest 10 records (`#12` down to `#3`) | Stats and newest-first 10-row limit verified | **PASS** |
| 19 | `test_check_textbee_diagnostics_verifies_device_belongs_and_enabled` | Mocked `GET /stats` and `GET /devices` with matching enabled device | Returns `success=True`, `device_found=True`, `device_enabled=True` | Returned `device_ready` for `Samsung Galaxy A54` | **PASS** |
| 20 | `test_check_textbee_diagnostics_detects_missing_or_disabled_device` | Mocked `GET /devices` with non-matching or disabled device | Detects `invalid_device` (`device_found=False`) and `device_unavailable` (`device_enabled=False`) | Both device diagnostic failure states detected | **PASS** |
| 21 | `test_gateway_status_indicator_configured_vs_unconfigured` | Configured vs. missing/placeholder `TEXTBEE_API_KEY` or `TEXTBEE_DEVICE_ID` | Displays `TextBee Gateway Configured` when configured and `Gateway Setup Required` when unconfigured | Header indicator switched accurately in all 3 cases | **PASS** |
| 22 | `test_timeout_seconds_parsing_for_missing_blank_invalid_nonpositive_and_valid` | `TEXTBEE_TIMEOUT_SECONDS` set to `None`, `""`, `"   "`, `"abc"`, `"0"`, `"-5"`, `"15"` | Defaults to `10` for missing/blank/invalid/`<= 0`, and returns `15` for `"15"` / `15` | All 10 timeout test inputs parsed as expected | **PASS** |
| 23 | `test_form_accessibility_attributes_on_invalid_and_valid_fields` | Unbound form vs. invalid `POST /` | Invalid fields include `aria-invalid="true"` and append `recipient-errors` / `message-errors` to `aria-describedby` | Accessibility attributes and matching error element IDs verified | **PASS** |

### B. Manual / Live Hardware Integration Test Summary (Separate from Mocked Suite)
- **Initial Hardware Diagnostic (Xiaomi China ROM)**: Our first test phone (`Redmi 24117RK2CC` running Xiaomi HyperOS China ROM `OS3.0.308.0.WOKCNXM`) authenticated with TextBee (`GET /api/v1/gateway/stats` & `GET /api/v1/gateway/devices` -> `HTTP 200 OK`), but outbound SMS jobs remained stuck at `status: dispatched` (`pushReceivedAt: None`) due to China ROM FCM push restrictions.
- **Verified Working Setup (Second Android Phone)**: We subsequently switched to another Android phone paired with TextBee (`TEXTBEE_API_KEY` and updated `TEXTBEE_DEVICE_ID` configured in `.env`).
- **Live End-to-End SMS Delivery**: Submitting a real SMS from the Django application queued the batch on TextBee (`smsBatchId`), dispatched it through the new Android gateway phone, and **confirmed real SMS receipt** on the authorized Philippine recipient's handset.

---

## 13. Known Limitations, Privacy & Security Considerations

### Known Limitations
1. **Asynchronous Handset Delivery Confirmation**: Calling `POST /api/v1/gateway/send-sms` queues the SMS batch (`smsBatchId`) for the paired Android device via Firebase Cloud Messaging (FCM). Because a local development server (`127.0.0.1:8000`) cannot receive public webhook callbacks without an external tunnel, the dashboard records the verified submission outcome (`Queued` / `Dispatched`) rather than claiming instant handset delivery.
2. **Android Device & Carrier Dependency**: Actual SMS transmission requires the paired Android gateway phone to remain powered on, connected to the internet (with active FCM connectivity), and loaded with an active SIM plan/balance.
3. **160-Character Application Limit**: The application enforces a 160-character limit per message in `SMSComposeForm` for simplicity; carrier segment calculation for multi-byte Unicode characters is out of scope for this assignment.

### Privacy & Security Considerations
- **Credential Isolation**: `DJANGO_SECRET_KEY`, `TEXTBEE_API_KEY`, and `TEXTBEE_DEVICE_ID` are read from environment variables (`django-sms/.env`) and excluded from version control via `.gitignore`.
- **Data Minimization in SQLite (`SMSLog`)**: Full recipient phone numbers and complete message bodies are never stored in SQLite; only masked phone numbers (`+639*****4567`), 48-character message excerpts, and safe status slugs are persisted.
- **Local Demonstration Scope**: Stored message excerpts should still be treated as potentially sensitive data. This application is designed as a single-user local classroom prototype (`127.0.0.1`) and must not be deployed to a public server without adding user authentication and access controls.
