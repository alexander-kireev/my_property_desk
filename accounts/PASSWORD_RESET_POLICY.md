# Public password reset policy

Approved for implementation on 8 October 2026. The public **Forgot password** flow and account pages now follow this policy, with the delivery limitation noted below.

## Reused account behavior

- A signed-in user can request a reset email from their profile. The public request page serves someone who cannot sign in.
- The email contains a token link to an existing password form. That form checks the token, applies the application's password validation, and sends the user to a completion page after success. Tests cover valid, expired, and reused links, and ensure rejected passwords are not kept in form state.
- `PASSWORD_RESET_TIMEOUT` is explicitly **3,600 seconds (one hour)**.
- Email delivery uses the configured Django email backend. Production delivery must be checked with the deployed mail configuration.

## Visitor journey

1. **Sign in → Forgot password.** Open a public request page with an empty email field. The field and form can ask browsers not to autofill, but browsers and password managers may ignore that preference.
2. **Request a link.** After submission, show the same confirmation message whether the address belongs to an active account or not: “If an account uses that email address, we’ll send a reset link.” Do not disclose account existence through validation, timing, or response details.
3. **Check email.** Send a single-use token link only for an eligible account. The email should explain the request, give the expiry period, and say that an unexpected message can be ignored. Use HTTPS links on the deployed site.
4. **Choose a password.** The link opens a page with new and confirm password fields. Apply the existing password validators. Never retain either password after a failed submission. An invalid, used, or expired link offers a way to request another.
5. **Finish.** After a successful change, show confirmation and a clear Sign in link. Do not automatically sign the user in. Previously issued reset links for the old password should no longer work.

## Security and operational rules

- The visitor-facing email and actual link expiry both use **one hour**.
- Request limits allow three requests per email address and 20 per `REMOTE_ADDR` in a one-hour window. The database-backed counters use hashes, so no raw address or IP is stored in them. Avoid recording raw reset tokens, passwords, or full reset URLs in application logs.
- Keep CSRF protection, the existing token validator, and server-side password validation. Do not accept an arbitrary post-reset redirect supplied in the request.
- Existing signed-in sessions become invalid after a password change; this is covered by a focused test.
- Test known and unknown addresses, invalid email syntax, rate limits, mail failure, valid/expired/reused tokens, password validation, and the public pages at mobile width. Check actual email delivery in the deployment environment.
- Use the public site's visual style for request, confirmation, password entry, and completion pages.

## Autofill preference

For the public sign-in, registration, reset-request, and password-entry forms, avoid server-side prepopulation of email and password values. Add `autocomplete="off"` hints where requested and verify the observed behavior in target browsers. Treat the hint as a preference rather than a guarantee: browsers and password managers may still offer saved credentials. Passwords must never be restored after a failed submission.

## Delivery limitation

Email is still sent synchronously through Django's configured backend. Known and unknown addresses receive the same page and redirect, but strict response-time equality cannot be guaranteed while real mail delivery happens during the request. A durable email queue would be needed to remove that timing difference. The deployment must also provide working SMTP and HTTPS.
