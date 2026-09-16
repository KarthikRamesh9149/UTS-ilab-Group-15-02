# Native harness integration checkpoint

`native_agents.agent_factory` constructs Terminus-2, OpenHands and custom
C0/C1/C2 adapters for `scored_trial.run_trial`. It requires explicit validated
output, temperature and reasoning settings; there are no scored-run defaults.
The test values (8,192 tokens, temperature 1, high reasoning) are fixture values,
not a frozen final protocol or a new spending allowance.

Baseline prompts, tools, context handling and loops remain inherited. No common
framework iteration count is imposed. The custom controller's explicit call
safety ceiling must be documented separately when selecting final settings.

Connection-only adjustments:

- Terminus outer retry wrapper and provider-client retries are disabled. The
  model gateway still never replays ambiguous requests.
- OpenHands uses its native installer structure with Python 3.12 and the four
  compatible package versions already used in the fixture. Its complete
  dependency resolution on official task images remains unqualified.
- The gateway canonicalises a single `reasoning_effort` alias to
  `reasoning.effort`; conflicting or unsupported aliases fail closed.
- Terminus LiteLLM silently dropped its constructor reasoning setting during
  the first on-wire test. Explicit request-body reasoning in the native
  `llm_call_kwargs` fixes that omission without changing the decision loop.
- The custom client accepts the same explicit temperature and reasoning values
  and uses the same 120-second HTTP timeout as the Terminus client.
- OpenHands 0.62.0's installed `LLMConfig.completion_kwargs` and environment
  parser were inspected in image
  `sha256:71fb65c3de9cae7a69de53e6af2a0d241bd5a296c7db10b76b6cd0fb10118f65`.
  The factory now sends explicit reasoning via `LLM_COMPLETION_KWARGS` and a
  120-second `LLM_TIMEOUT`. This is configuration, not a patched native loop.

Evidence: real native constructors; actual Terminus and custom client HTTP
serialization into a synthetic provider; local installer-command and factory
tests. No live API calls or paid benchmark trials were made for this checkpoint.

`scored_runtime_probe --harness openhands` is prepared for the next serialized
Docker check. Its synthetic provider requires high reasoning, temperature 1 and
8,192 output tokens on actual incoming requests. The native OpenHands agent must
execute a marker-writing tool call, finish, and pass Harbor verification with two
reconciled synthetic receipts. The preinstalled fixture skips installation only;
production installation into official task images is still a separate gate.
This native test has not run yet and must not be called qualified from unit tests.

Remaining admission requirements: rebuild the gateway image with this source;
qualify the new scored runner in Docker; test actual OpenHands outgoing settings
(including reasoning and retry behaviour); freeze and enforce protocol settings
at the common gateway; complete billing reconciliation and matrix admission;
qualify live native OpenHands/custom calls within the existing setup allowance.
Do not interpret the local tests as permission to skip these execution gates.
