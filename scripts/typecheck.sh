#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Each container deliberately exports its own app package. Isolate the
# package roots per invocation so mypy sees exactly the deployed imports.
for service in services/social-analytics/instagram services/content-automation/generator services/api-gateway; do
  MYPYPATH="libs/common:$service" python -m mypy "$service/app" libs/common/common
done
