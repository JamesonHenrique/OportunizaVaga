#!/bin/bash
# Run the offline Node suite through the existing CI test_*.sh discovery.
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
node --test "$ROOT/tests/nova-senha.test.mjs"
