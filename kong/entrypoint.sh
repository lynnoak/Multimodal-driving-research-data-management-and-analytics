#!/bin/sh
set -eu
GATEWAY_API_KEY=${GATEWAY_API_KEY:-${APTICONDUITE_API_KEY:-}}
case "$GATEWAY_API_KEY" in
  ''|*[!a-zA-Z0-9_-]*) echo "API key must contain only letters, digits, underscore or hyphen" >&2; exit 1 ;;
esac
if [ "${#GATEWAY_API_KEY}" -lt 32 ]; then
  echo "API key must contain at least 32 characters" >&2; exit 1
fi
case "${API_RATE_LIMIT_PER_MINUTE:-}" in
  ''|*[!0-9]*) echo "Rate limit must be a positive integer" >&2; exit 1 ;;
esac
if [ "$API_RATE_LIMIT_PER_MINUTE" -lt 1 ]; then
  echo "Rate limit must be positive" >&2; exit 1
fi
umask 077
sed -e "s/__API_KEY__/$GATEWAY_API_KEY/g" \
    -e "s/__RATE_LIMIT__/$API_RATE_LIMIT_PER_MINUTE/g" \
    /etc/kong/kong.template.yml > /tmp/kong.yml
exec /docker-entrypoint.sh "$@"
