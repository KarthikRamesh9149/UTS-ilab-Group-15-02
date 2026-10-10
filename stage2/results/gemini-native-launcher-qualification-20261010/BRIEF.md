# Gemini native launcher qualification — 10 October 2026

The user selected option 2: up to twenty Terminus-2 attempts and twenty
OpenHands attempts under the original shared US$20 cap.

- 57 affected offline checks passed without external network or a provider key.
- Both native Docker lifecycles passed through the actual launcher and a local
  fake upstream. Terminus made three scripted requests; OpenHands made two.
- The immutable prior ledger was retained. Fake costs were zero. Budget-denial
  checks dispatched no request to the fake upstream.
- Both lifecycles revoked model access before verification and removed their
  task containers. No cleanup or metadata trace errors were observed.
- The final run qualifies the current source hashes, bundle and controller image
  recorded in qualification.json. An earlier passing source snapshot is retained
  privately; the final snapshot adds capacity admission and failed-start traces.

These are synthetic marker checks, not benchmark scores. No paid native
benchmark attempt was used for qualification. Raw logs stay private. Paid
results are delivered separately under gemini-native-dev20-laptop-20261010.
Local Langfuse metadata readback is delivered after its services restart.
