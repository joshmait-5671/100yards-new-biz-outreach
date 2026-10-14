# Stop the Bus — landing page

Replacement for the Kit-hosted page at `monkey-bars-learning.kit.com/stop-the-bus`.
Static page on Netlify, on brand, with signups landing in a Google Sheet.

```
monkey-bars-stop-the-bus/
├── index.html                      the page (all copy marked "COPY SLOT")
├── netlify/functions/subscribe.js  writes to the Sheet + Kit
├── apps-script.gs                  paste into the Google Sheet's Apps Script
├── deploy.sh                       staged deploy, explicit --site
└── netlify.toml
```

## Where a signup goes

Three independent captures. An email has to lose all three to disappear.

| | What | Fails how |
|---|---|---|
| 1 | **Netlify Forms** — browser posts the form natively | Only if Netlify itself is down |
| 2 | **Google Sheet** — function → Apps Script web app | If the script URL or secret is wrong |
| 3 | **Kit** — function → Kit v4 API | If the API key or form ID is wrong |

Legs 2 and 3 run in parallel and neither can block the other. Leg 1 needs no
configuration at all and works the moment the site deploys — so the page is
safe to put in front of teachers before the Sheet or Kit is wired up.

Netlify Forms also exports straight to CSV, which opens in Excel. That is the
redundancy: if the Sheet write ever silently breaks, the same emails are sitting
in the Netlify dashboard under **Forms → stop-the-bus**.

## Setup

**1. Deploy the site**

```bash
./deploy.sh --prod
```

First run has no site ID, so the CLI offers to create one. Paste the ID it prints
into `SITE_ID` at the top of `deploy.sh`, and add it to
`reference_netlify_site_ids.md` in memory.

**2. Turn on Netlify Forms** — Site settings → Forms → enable form detection,
then redeploy once. Add a notification email so each signup also hits an inbox.

**3. Wire the Google Sheet**

- New Sheet → Extensions → Apps Script → paste `apps-script.gs`
- Project Settings → Script Properties → add `SHEET_SECRET` (any long random string)
- Deploy → New deployment → Web app, *Execute as: Me*, *Who has access: Anyone*
- Copy the `/exec` URL

**4. Set environment variables** — Netlify → Site settings → Environment variables:

| Key | Value |
|---|---|
| `SHEET_WEBHOOK_URL` | the Apps Script `/exec` URL |
| `SHEET_SECRET` | same string as the Script Property |
| `KIT_API_KEY` | Kit → Settings → Developer → V4 API key |
| `KIT_FORM_ID` | the numeric ID of the Stop the Bus form in Kit |

Any variable left unset is skipped, not failed — the other legs still run.

**5. Verify**

```bash
curl -s -o /dev/null -w '%{http_code}\n' <production URL>

curl -X POST <production URL>/.netlify/functions/subscribe \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","firstName":"Test"}'
```

The second call returns which legs wrote and which were skipped. Then confirm
the row appears in the Sheet and the subscriber appears in Kit.

## Keeping Kit

Kit stays the sender. It still owns the welcome email that delivers the PDF and
every sequence after it — this only replaces the *page*, because Kit's page
builder won't take the brand. If the Kit leg is left unconfigured, signups still
reach the Sheet but nobody gets the PDF automatically.

## Editing copy

Every piece of text sits under an HTML comment marked `COPY SLOT`. The brand
tokens are the `:root` block at the top of `index.html`:

```
--yellow #FFD401   --ink #111317   --cream #FCFBF6   --blue #2F39D0
```

Headline face is Archivo 900, uppercase, tight tracking — the closest web font
to the brand's Canva headlines.

## Deploy rules

`deploy.sh` stages into `/private/tmp` first and always passes `--site` and
`--functions` explicitly. Both of those are deliberate: a bare deploy inside the
Claude tree inherits a stray parent `.netlify` link and publishes to the wrong
site, and `--dir` makes Netlify ignore `netlify.toml`, so functions silently
don't ship unless `--functions` is passed too.

While iterating, send the **unique deploy URL** from the CLI output, not the
production URL — the production URL caches and shows stale copy.
