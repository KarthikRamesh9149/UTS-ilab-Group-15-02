#!/bin/bash
set -eu
if [ "$(cat /tmp/uts-lifecycle-result)" = "UTS_LIFECYCLE_OK" ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
