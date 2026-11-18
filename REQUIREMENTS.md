# Requirements — Django SMS Group Assignment

**Course:** IT 120 – Integrative Programming and Technologies
**Group size:** Maximum 3 members
**Assignment:** Build a Django Application for Sending SMS
**Deadline:** Instructor confirmation required; the PDF mentions November 20, 2026 as the original deadline.

## Required (from instructor's PDF)

### Core functionality
- [x] Django web app with a recipient phone number input, message input, and Send SMS button.
- [x] On submission, validate inputs and send an SMS request through a configured SMS provider (TextBee v1 REST API).
- [x] Show understandable success/failure feedback, including rejected submissions.
- [x] Handle missing phone, empty message, invalid phone, missing/incorrect credentials, provider/network errors.
- [x] Use a readable, organized interface.

### Security
- [x] Read API credentials from environment variables or equivalent secure configuration.
- [x] Never commit actual credentials or publish them in the video/screenshots.
- [x] Preserve Django CSRF protection.
- [x] Test only with authorized recipients and comply with provider restrictions.
- [x] Do not claim SMS was delivered unless delivery is confirmed; distinguish submission from delivery.

### Testing and handoff
- [x] Test valid input, missing phone, missing message, invalid phone, incorrect/missing credentials, provider/network failure, success response.
- [x] Record test results and resolve significant defects.
- [ ] Create GitHub repository with application source, requirements.txt, README, and safe configuration guidance. *(Source, requirements.txt, and README ready for GitHub push.)*
- [x] Add .gitignore for secrets, local virtual environment, and generated files.
- [ ] Record a 3–10 minute video: intro, UI, sending attempt to authorized number, result feedback, one validation/error case, extra feature(s), technologies and member contributions.
- [ ] Submit repository and video link by email to `prala-an@carsu.edu.ph`, subject `Assignment_IT 120-1stSemSY26-27`.

## Optional enhancements (proposed, NOT instructor-mandated)
Choose at least one functional feature beyond core SMS sending:
- [x] SMS attempt history stored in SQLite (`SMSLog` with masked recipients and short excerpts).
- [x] Message character counter and preview.
- [x] Simple dashboard of submitted/failed attempts (`Total Attempts`, `Submitted`, `Failed`).

## Suggested scope decisions
- Use Django templates + plain CSS, SQLite, and the TextBee v1 REST API (`https://api.textbee.dev/api/v1/gateway/send-sms`) via Python `requests`.
- No login system or React frontend for the first version.
- Avoid exposing full recipient numbers in history; mask them in the interface.
- A provider `queued` / `smsBatchId` response is NOT a handset delivery confirmation.
- Test with mocks first and use an authorized Philippine recipient for manual demonstration.

## Acceptance criteria
1. The Django project starts locally and serves the form.
2. Invalid inputs do not call the provider and show actionable errors.
3. Valid inputs call the configured provider once and show its actual submission outcome.
4. Provider errors never disclose secrets and do not crash the app.
5. Unit tests mock outbound SMS calls; manual demonstration verifies the real integration.
6. A fresh group member can follow README to run the app without private credentials in the repository.
