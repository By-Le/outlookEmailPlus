# Outlook Email Plus

A web application for unified Outlook / IMAP mailbox management, email reading, verification code extraction, and mail pool orchestration for registration and automation workflows.

[中文 README](./README.md) | [English README](./README.en.md)

## Why This Project

- Manage Outlook OAuth mailboxes and IMAP mailboxes in one interface to avoid switching between multiple tools.
- Go beyond a simple inbox viewer with built-in support for verification code extraction, link extraction, and mail-pool-based workflow automation.
- Support bulk import, groups, tags, and search for long-term multi-account maintenance.
- Start locally in minutes or deploy with Docker at low operational cost.
- Provide controlled external APIs and mail pool capabilities for registration, verification, and automation scripts.

## Core Features

- Multi-mailbox account management with bulk import, groups, tags, and search
- Outlook OAuth and IMAP integration for multiple mailbox providers
- Email reading and verification code extraction for registration, login, and verification scenarios
- Mail pool management with claim, release, completion, and status transitions
- Optional extensions such as Telegram notifications, temporary mailboxes, and controlled external APIs

## Typical Use Cases

- Maintain multiple Outlook / IMAP mailbox accounts from one place
- Process registration codes, verification links, and notification emails at scale
- Connect mailbox accounts to a mail pool for external job claiming and recycling
- Expose controlled mail capabilities to internal scripts or automation systems

## Deployment

### Docker

```bash
docker pull ghcr.io/zeropointsix/outlook-email-plus:latest

docker run -d \
  --name outlook-email-plus \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e SECRET_KEY=your-secret-key-here \
  -e LOGIN_PASSWORD=your-login-password \
  -e ALLOW_LOGIN_PASSWORD_CHANGE=false \
  ghcr.io/zeropointsix/outlook-email-plus:latest
```

Notes:

- Mount `data/` for persistence.
- Use a stable and secure value for `SECRET_KEY`.

### Local Setup

```bash
python -m venv .venv
pip install -r requirements.txt
python start.py
```

Common environment variables:

- `SECRET_KEY`: encryption key for sessions and sensitive fields
- `LOGIN_PASSWORD`: admin login password
- `ALLOW_LOGIN_PASSWORD_CHANGE`: whether the login password can be changed in Settings; set `false` for demo sites
- `DATABASE_PATH`: SQLite database path
- `OAUTH_CLIENT_ID`: Outlook OAuth application ID
- `OAUTH_REDIRECT_URI`: Outlook OAuth callback URL

### Email Notification Configuration

If you want to enable the built-in email notification channel, you must configure a dedicated SMTP service for business notifications. This is separate from GPTMail and Telegram and cannot be substituted by either of them.

Minimum required variables:

- `EMAIL_NOTIFICATION_SMTP_HOST`: SMTP server host
- `EMAIL_NOTIFICATION_FROM`: sender email address

Common optional variables:

- `EMAIL_NOTIFICATION_SMTP_PORT`: SMTP port, default `25`
- `EMAIL_NOTIFICATION_SMTP_USERNAME`: SMTP login username
- `EMAIL_NOTIFICATION_SMTP_PASSWORD`: SMTP login password or app-specific password
- `EMAIL_NOTIFICATION_SMTP_USE_TLS`: enable STARTTLS
- `EMAIL_NOTIFICATION_SMTP_USE_SSL`: enable SSL
- `EMAIL_NOTIFICATION_SMTP_TIMEOUT`: SMTP timeout in seconds, default `15`

Example:

```env
EMAIL_NOTIFICATION_SMTP_HOST=smtp.qq.com
EMAIL_NOTIFICATION_SMTP_PORT=465
EMAIL_NOTIFICATION_FROM=your_account@qq.com
EMAIL_NOTIFICATION_SMTP_USERNAME=your_account@qq.com
EMAIL_NOTIFICATION_SMTP_PASSWORD=your_smtp_auth_code
EMAIL_NOTIFICATION_SMTP_USE_SSL=true
EMAIL_NOTIFICATION_SMTP_USE_TLS=false
EMAIL_NOTIFICATION_SMTP_TIMEOUT=15
```

Common error codes:

- `EMAIL_NOTIFICATION_SERVICE_UNAVAILABLE`
  Meaning: the system does not have a usable SMTP configuration for email notifications. The most common cause is missing `EMAIL_NOTIFICATION_SMTP_HOST` or `EMAIL_NOTIFICATION_FROM`.
- `EMAIL_NOTIFICATION_SMTP_PORT_INVALID`
  Meaning: `EMAIL_NOTIFICATION_SMTP_PORT` is not a valid positive integer.
- `EMAIL_NOTIFICATION_SMTP_TIMEOUT_INVALID`
  Meaning: `EMAIL_NOTIFICATION_SMTP_TIMEOUT` is not a valid positive integer.
- `EMAIL_NOTIFICATION_RECIPIENT_REQUIRED`
  Meaning: email notifications were enabled in settings, but the recipient email address was left empty.
- `EMAIL_NOTIFICATION_RECIPIENT_NOT_CONFIGURED`
  Meaning: the “Send Test Email” action could not find a saved notification recipient.

Important behavior:

- The settings page follows a “save first, then test” rule.
- The test endpoint does not read a temporary recipient from the input field.
- It only uses the persisted `email_notification_recipient` in settings.
- The correct flow is: save the recipient first, then click “Send Test Email”.

## UI Preview

![Dashboard](img/仪表盘.png)
![Mailbox View](img/邮箱界面.png)
![Verification Code Extraction](img/提取验证码.png)
![Settings](img/设置界面.png)

## Project Documentation

- [Documentation Index](./docs/INDEX.md)
- [Registration Worker and Mail Pool API](./docs/API/registration-mail-pool-api.en.md)
- [中文注册与邮箱池接口文档](./docs/API/注册与邮箱池接口文档.md)

If you need to connect registration workers or other batch automation jobs, start with the document above.

The current worker integration contract is:

- Path prefix: `/api/external/pool/*`
- Auth header: `X-API-Key`
- The old anonymous `/api/pool/*` endpoints have been removed

## Acknowledgements

This project is built on the following open-source technologies and service capabilities:

- Flask
- SQLite
- Microsoft Graph API
- IMAP
- APScheduler

The following reference projects also provided useful ideas and inspiration:

- [assast/outlookEmail](https://github.com/assast/outlookEmail)
- [gblaowang-i/MailAggregator_Pro](https://github.com/gblaowang-i/MailAggregator_Pro)

## License

Apache License 2.0
