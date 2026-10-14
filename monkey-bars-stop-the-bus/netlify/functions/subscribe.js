// Stop the Bus — signup handler.
//
// Writes each signup to two places and does not care if one of them is having a bad day:
//   1. Google Sheet  (the spreadsheet Kira actually opens)   — via an Apps Script web app
//   2. Kit            (so her existing sequences still deliver the PDF)
//
// Netlify Forms is a third capture that happens in the browser, outside this file.
// So an email has to lose all three races to actually disappear.
//
// Env vars (Netlify → Site settings → Environment variables):
//   SHEET_WEBHOOK_URL   Apps Script /exec URL          (required for the Sheet)
//   SHEET_SECRET        shared string, must match Apps Script
//   KIT_API_KEY         Kit v4 API key                 (required for Kit)
//   KIT_FORM_ID         Kit form ID to subscribe into
//
// Missing env vars are not an error. A leg with no config is simply skipped and
// reported as "skipped", so the page keeps working while Kira wires things up.

const TIMEOUT_MS = 8000;

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
    ),
  ]);
}

function isValidEmail(value) {
  return typeof value === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value.trim());
}

async function writeToSheet({ email, firstName, source, userAgent }) {
  const url = process.env.SHEET_WEBHOOK_URL;
  if (!url) return { ok: false, skipped: true, reason: 'SHEET_WEBHOOK_URL not set' };

  const res = await withTimeout(
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        secret: process.env.SHEET_SECRET || '',
        timestamp: new Date().toISOString(),
        email,
        firstName,
        source,
        userAgent,
      }),
    }),
    TIMEOUT_MS,
    'Google Sheet'
  );

  // Apps Script answers 200 with a JSON body, or 302 to a redirect it wants followed.
  if (!res.ok) {
    throw new Error(`Sheet responded ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
  return { ok: true };
}

async function writeToKit({ email, firstName }) {
  const apiKey = process.env.KIT_API_KEY;
  const formId = process.env.KIT_FORM_ID;
  if (!apiKey || !formId) {
    return { ok: false, skipped: true, reason: 'KIT_API_KEY or KIT_FORM_ID not set' };
  }

  const res = await withTimeout(
    fetch(`https://api.kit.com/v4/forms/${encodeURIComponent(formId)}/subscribers`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Kit-Api-Key': apiKey,
      },
      body: JSON.stringify({
        email_address: email,
        first_name: firstName || undefined,
      }),
    }),
    TIMEOUT_MS,
    'Kit'
  );

  if (!res.ok) {
    throw new Error(`Kit responded ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
  return { ok: true };
}

export default async (request) => {
  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json', Allow: 'POST' },
    });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const email = String(body.email || '').trim().toLowerCase();
  const firstName = String(body.firstName || '').trim().slice(0, 80);

  // Honeypot. Bots fill it, humans never see it. Answer 200 so the bot stops retrying.
  if (String(body.company || '').trim()) {
    console.log('Honeypot tripped, discarding submission');
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  if (!isValidEmail(email)) {
    return new Response(JSON.stringify({ error: 'A valid email is required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const context = {
    email,
    firstName,
    source: 'stop-the-bus',
    userAgent: request.headers.get('user-agent') || '',
  };

  const [sheet, kit] = await Promise.allSettled([
    writeToSheet(context),
    writeToKit(context),
  ]);

  const describe = (settled) =>
    settled.status === 'fulfilled'
      ? settled.value
      : { ok: false, error: settled.reason?.message || String(settled.reason) };

  const result = { sheet: describe(sheet), kit: describe(kit) };

  // Log failures loudly — Netlify function logs are where Kira's "where did that
  // signup go" question gets answered.
  for (const [name, r] of Object.entries(result)) {
    if (!r.ok && !r.skipped) console.error(`[${name}] FAILED for ${email}: ${r.error}`);
    if (r.skipped) console.warn(`[${name}] skipped: ${r.reason}`);
  }

  const anyWrote = result.sheet.ok || result.kit.ok;

  // 200 when something stored it, 207 when nothing here did. Either way the browser
  // has already handed the same email to Netlify Forms, so the reader sees success.
  return new Response(JSON.stringify({ ok: anyWrote, result }), {
    status: anyWrote ? 200 : 207,
    headers: { 'Content-Type': 'application/json' },
  });
};
