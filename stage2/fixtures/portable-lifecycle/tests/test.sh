#!/bin/bash
set -eu
echo 0 > /logs/verifier/reward.txt
test "$(cat /tmp/uts-lifecycle-result)" = UTS_LIFECYCLE_OK
test "$(head -n 1 /tmp/uts-long.txt)" = edited-first-row
test "$(tail -n 1 /tmp/uts-long.txt)" = row-15999
test "$(wc -l < /tmp/uts-long.txt)" -eq 16000
test "$(cat /tmp/uts-timeout-result)" = 124
kill -0 "$(cat /tmp/uts-background.pid)"
echo 1 > /logs/verifier/reward.txt
