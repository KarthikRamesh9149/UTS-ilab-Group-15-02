# Shared model protocol enforcement

Model settings now have a pure shared representation used by native factories,
the single-trial runner and the scored gateway. The runner persists a private
`model-protocol.json` once per study runtime. Subsequent trials must match it;
the gateway service refuses to start without it. This does not freeze a paid
protocol yet: only isolated synthetic test runtimes have been populated.

Before reservation or dispatch the scored gateway rejects model/output-limit,
temperature, reasoning and sampling drift. A shorter output request is allowed
within the common maximum (for native context handling); no client may exceed
that maximum. Nucleus sampling defaults uniformly to 1.0 when omitted, and a
different supplied value or unregistered seed is rejected. Message history,
native tool schemas and baseline decision loops are not changed by this check.

Protocol fingerprints are included in gateway and runner trial evidence. The
post-trial billing audit rechecks both the fingerprint and saved outgoing request
settings. Lower-level setup/unit fixtures may explicitly use the generic gateway
without this scored policy; the production `serve` entry point cannot.

Verification: 147 stage-two tests passed, including five protocol tests checking
immutability, missing configuration, parameter drift before billing, and
preservation of messages. The fixture temperature/output values remain test
parameters, not final scoring choices. Paid admission, native container tests
and the empirical qualification gate remain outstanding.
