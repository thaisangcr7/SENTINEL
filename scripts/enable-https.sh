#!/usr/bin/env bash
#
# Put SENTINEL behind HTTPS at api.sangthai.dev, using Caddy as a reverse proxy
# in front of the FastAPI app. Caddy obtains and renews the certificate itself.
#
# Run it ON the instance, from your laptop, in one line:
#
#   ssh ubuntu@52.23.231.90 'sudo bash -s' < scripts/enable-https.sh
#
# Two things must already be true, in this order:
#
#   1. api.sangthai.dev has an A record pointing at this instance's public IP,
#      with Cloudflare proxying OFF (grey cloud, "DNS only"). Let's Encrypt has
#      to reach this box directly to verify the domain; an orange-cloud record
#      answers on Cloudflare's IPs instead and validation fails.
#
#   2. Ports 80 and 443 are open in sentinel-sg. That is declared in
#      terraform/main.tf — apply it before running this.
#
# The script is safe to run twice.

set -euo pipefail

DOMAIN="api.sangthai.dev"
APP_PORT="8000"

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
fail() { printf '\n\033[31mFAILED: %s\033[0m\n' "$1" >&2; exit 1; }

log "Checking that ${DOMAIN} points at this machine"
# IMDSv2 — a token is required on newer instances.
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
          -H "X-aws-ec2-metadata-token-ttl-seconds: 60" --max-time 5 || true)
MY_IP=$(curl -s --max-time 5 \
          ${TOKEN:+-H "X-aws-ec2-metadata-token: $TOKEN"} \
          http://169.254.169.254/latest/meta-data/public-ipv4 || true)
DNS_IP=$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)

[ -n "$DNS_IP" ] || fail "${DOMAIN} does not resolve yet. Add the A record first, then wait a minute."
if [ -n "$MY_IP" ] && [ "$DNS_IP" != "$MY_IP" ]; then
  fail "${DOMAIN} resolves to ${DNS_IP}, but this instance is ${MY_IP}.
       If ${DNS_IP} looks like a Cloudflare address, the record is proxied —
       set it to DNS only (grey cloud) and try again."
fi
echo "    ${DOMAIN} -> ${DNS_IP}  (this instance)"

log "Installing Caddy"
if ! command -v caddy >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq
  apt-get install -y -qq caddy
else
  echo "    already installed: $(caddy version)"
fi

log "Writing /etc/caddy/Caddyfile"
cat > /etc/caddy/Caddyfile <<EOF
# Terminates TLS for SENTINEL and forwards to the FastAPI app on localhost.
# Caddy requests the certificate on first start and renews it automatically.
${DOMAIN} {
    reverse_proxy localhost:${APP_PORT}
}
EOF
caddy validate --config /etc/caddy/Caddyfile >/dev/null || fail "Caddyfile is invalid"

log "Reloading Caddy and requesting the certificate"
systemctl enable --now caddy
systemctl reload caddy || systemctl restart caddy

# The first certificate can take a few seconds to arrive.
for i in $(seq 1 12); do
  sleep 5
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://${DOMAIN}/docs" || true)
  echo "    attempt ${i}: HTTPS returned ${code}"
  [ "$code" = "200" ] && { log "Done — https://${DOMAIN}/docs is live"; exit 0; }
done

fail "No certificate after a minute. Check: journalctl -u caddy --no-pager -n 40"
