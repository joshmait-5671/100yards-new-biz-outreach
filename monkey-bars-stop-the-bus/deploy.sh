#!/usr/bin/env bash
# Stop the Bus — deploy to Netlify.
#
# Run from anywhere. Stages into /private/tmp first because deploys launched from
# inside ~/Desktop/Claude hang at 0% CPU (see feedback_netlify_deploy_from_staging_dir).
#
#   ./deploy.sh              draft deploy, prints a preview URL
#   ./deploy.sh --prod       production deploy
#
# Needs $NETLIFY_AUTH_TOKEN (in ~/.zshrc) and SITE_ID below.

set -euo pipefail

SITE_ID="${MONKEY_BARS_SITE_ID:-}"      # paste the site ID here after first deploy
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGE="/private/tmp/stop-the-bus-deploy"

if [ -z "${NETLIFY_AUTH_TOKEN:-}" ]; then
  echo "NETLIFY_AUTH_TOKEN is not set. It lives in ~/.zshrc." >&2
  exit 1
fi

rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$SRC/index.html" "$SRC/netlify.toml" "$SRC/package.json" "$STAGE/"
cp -R "$SRC/netlify" "$STAGE/netlify"
[ -d "$SRC/assets" ] && cp -R "$SRC/assets" "$STAGE/assets"

cd "$STAGE"

ARGS=(deploy --auth "$NETLIFY_AUTH_TOKEN" --dir "$STAGE" --functions "$STAGE/netlify/functions")

if [ -n "$SITE_ID" ]; then
  ARGS+=(--site "$SITE_ID")
else
  echo "No SITE_ID set — the CLI will prompt you to create a new site."
  echo "Save the ID it prints into SITE_ID at the top of this script."
fi

[ "${1:-}" = "--prod" ] && ARGS+=(--prod)

PATH="/usr/local/bin:/opt/homebrew/bin:$PATH" npx --yes netlify-cli "${ARGS[@]}"

echo
echo "Deploy finished. Verify before trusting it:"
echo "  curl -s -o /dev/null -w '%{http_code}\n' <the URL printed above>"
