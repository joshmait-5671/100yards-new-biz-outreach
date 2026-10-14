/**
 * Stop the Bus — Google Sheet writer.
 *
 * Deploy: Extensions > Apps Script in the destination Sheet, paste this in,
 * then Deploy > New deployment > Web app:
 *     Execute as:       Me
 *     Who has access:   Anyone
 * Copy the /exec URL into Netlify as SHEET_WEBHOOK_URL.
 *
 * Set SHEET_SECRET to the same string in BOTH places:
 *   - Apps Script: Project Settings > Script Properties > SHEET_SECRET
 *   - Netlify:     Environment variables > SHEET_SECRET
 */

var SHEET_NAME = 'Signups';
var HEADERS = ['Timestamp', 'Email', 'First name', 'Source', 'User agent'];

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);

    var expected = PropertiesService.getScriptProperties().getProperty('SHEET_SECRET');
    if (expected && body.secret !== expected) {
      return json({ ok: false, error: 'bad secret' });
    }

    if (!body.email) {
      return json({ ok: false, error: 'email required' });
    }

    var sheet = getSheet();
    sheet.appendRow([
      body.timestamp || new Date().toISOString(),
      body.email,
      body.firstName || '',
      body.source || '',
      body.userAgent || ''
    ]);

    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

function getSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);

  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
