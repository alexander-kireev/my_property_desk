# Cloudflare Web Analytics decision

Decision date: 8 October 2026.

Use **Cloudflare Web Analytics, manually embedded**, for aggregate visits and performance on the home, features, FAQ, coming-soon and privacy pages. Do not load the beacon on contact, account, reset-link or workspace pages. Do not use advertising, visitor profiles, custom events or cross-site tracking.

## UK visitor choice

This limited use is intended to meet the UK PECR statistical-purpose exception. The ICO says a qualifying statistics tool does not require prior consent, but visitors must receive clear information and a simple, free way to object. The public privacy notice describes the use and has a one-click off/on control. The opt-out is stored for one year in an HTTP-only preference cookie; the server then omits the Cloudflare beacon on future page loads. The preference cookie is used only to remember the objection. No consent banner is used for this configuration. Reassess this decision before changing the analytics product or its purpose.

Cloudflare says Web Analytics does not use cookies or local storage for metrics, does not log URL query strings, retains unsampled beacon data for seven days, and offers six months of Web Analytics reports. “Cookie-free” alone is not the legal reason for omitting a consent banner: the ICO also treats scripts that access device information as storage/access technologies.

## Deployment setup

1. Add the exact public hostname to Cloudflare Web Analytics and copy its **site token**, not an API key. Set `PMS_CLOUDFLARE_WEB_ANALYTICS_TOKEN` on the Render service. With no token, the beacon is absent.
2. Use Cloudflare's manual JS-snippet mode. If the domain is proxied through Cloudflare, **turn off automatic beacon injection** (choose manual snippet installation in Manage Site). Automatic injection can add the beacon to account pages and bypass the opt-out.
3. Verify the live site in browser network tools: the beacon loads on the five selected pages, is absent on contact/account/workspace pages, and stops loading after the privacy-page opt-out. Test again after clearing cookies and after turning analytics back on.
4. Confirm the final hostnames, provider regions, international-transfer details, email provider and log/email retention settings before deployment. Update the privacy notice if the deployed facts differ.

The opt-out controls this site's JavaScript beacon. It does not suppress normal web-server, security or CDN request logs, which are covered separately in the privacy notice.

Sources: [ICO statistical-purpose exception](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/), [ICO scripts and tags](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-storage-and-access-technologies/), [Cloudflare setup modes](https://developers.cloudflare.com/web-analytics/get-started/), [Cloudflare Web Analytics FAQ](https://developers.cloudflare.com/web-analytics/faq/), [Cloudflare dimensions](https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/).
