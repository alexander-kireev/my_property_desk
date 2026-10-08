# My Property Desk production setup

Target: one paid Render web service in Frankfurt, a Neon PostgreSQL database, Resend SMTP delivery, Squarespace email forwarding, and `mypropertydesk.co.uk`. The repository's `render.yaml` prepares the web service; it does not create the external Neon database, email forwarding rule, DNS records or Cloudflare Web Analytics site.

## Render and Neon

1. Create the Neon database in a suitable EU region and copy its database name, user, password and hostname into the Render environment variables prompted by `render.yaml`. Keep `PMS_DB_SSLMODE=require`. Use the database connection details from Neon, not local PostgreSQL values.
2. Create the Render Blueprint from `render.yaml` on `main` when we are ready to deploy. Automatic deploys are off, so later releases require an explicit deploy. It installs dependencies and collects static files during the build, applies migrations in Render's pre-deploy phase, then starts Gunicorn with two workers. `/health/` is the lightweight web health check; it deliberately does not query the database.
3. Set `PMS_ALLOWED_HOSTS` to `mypropertydesk.co.uk` and the actual Render hostname, separated by commas. Set `PMS_CSRF_TRUSTED_ORIGINS` to `https://mypropertydesk.co.uk` and the corresponding Render HTTPS origin. `PMS_PRODUCTION=True` rejects debug mode and enables HTTPS-aware cookies, proxy scheme handling and a short initial HSTS period. Increase HSTS only after the custom hostname is working reliably over HTTPS; subdomain-wide HSTS and preload stay off.
4. Add the custom domain to Render, then create the DNS record requested by Render in Squarespace DNS. Wait for Render to issue its TLS certificate before testing sign-in or password reset links.
5. In Squarespace's Email Forwarding section for `mypropertydesk.co.uk`, forward `support@mypropertydesk.co.uk` to the private Gmail destination and verify that address. Test from a separate inbox; Squarespace says forwarding can take 24–48 hours to begin after verification. Configure Resend for sending from the domain, without enabling Resend inbound routing or replacing Squarespace's forwarding MX records. In Render, set `PMS_EMAIL_HOST=smtp.resend.com`, `PMS_EMAIL_PORT=587`, `PMS_EMAIL_HOST_USER=resend`, `PMS_EMAIL_HOST_PASSWORD` to the Resend API key, `PMS_EMAIL_USE_TLS=True`, and `PMS_EMAIL_USE_SSL=False`. Set `PMS_DEFAULT_FROM_EMAIL` and `PMS_CONTACT_EMAIL` to `support@mypropertydesk.co.uk`. Production settings refuse to start with the console backend, missing SMTP credentials or local placeholder addresses. Test registration, password reset, contact and account-change emails with real addresses.
6. Add the Cloudflare Web Analytics site token as `PMS_CLOUDFLARE_WEB_ANALYTICS_TOKEN`. Use manual snippet mode and disable Cloudflare's automatic injection so that the site's page restrictions and analytics opt-out remain effective. See `legal/ANALYTICS_DECISION.md`.

`PMS_REGISTRATION_MODE=instant` is selected in `render.yaml`. Set it to `pending` if email-confirmed registration is wanted later. The existing pending flow stays in the codebase.

## Release checks

- Run `python manage.py check --deploy` with production environment values. Warnings about HSTS subdomains and preload are intentional during the initial rollout: the app does not assert HTTPS for possible child hosts beneath `mypropertydesk.co.uk`, and it has not been submitted for browser preloading.
- Confirm `/health/` returns 200, static assets load with `DEBUG=False`, and unknown paths use the custom 404 page.
- Confirm HTTPS links, CSRF-protected forms, secure cookies and both registration modes in a production-like environment.
- Confirm the privacy notice's named providers, transfer details and retention descriptions against the selected service settings before public launch.

References: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Render pre-deploy and health checks](https://render.com/docs/deploys), [WhiteNoise Django setup](https://whitenoise.readthedocs.io/en/stable/django.html), [Neon PostgreSQL connection guidance](https://neon.com/blog/python-django-and-neons-serverless-postgres).
