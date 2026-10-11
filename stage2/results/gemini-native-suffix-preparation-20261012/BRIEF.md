# Native suffix preparation — no paid run

The remaining twenty-two native attempts have not started. This preparation preserves the existing US$50 total cap, all 3,010 predecessor requests, the eighteen recorded native outcomes, and both US$1.10 unknown-charge reserves. It grants no additional allowance and cannot start paid execution.

## Implementation and checks

`gemini_same_cap.py` admits only the exact unstarted suffix of the hash-bound closed outcomes and copies the predecessor ledger without applying another budget amendment. The launcher accepts `--same-cap-manifest` only together with `--qualify` and closed evidence. Agent loops, model settings and official task resources are unchanged. Python source and the lifecycle verifier use LF line endings through `.gitattributes`.

All **67 selected offline checks** passed, including fifteen new admission checks. Checks cover unchanged cap and authorization, preservation of both reserves, rejection of completed trials and modified evidence, live-credit limits, budget exhaustion, and rejection of paid execution through the preparation flag.

| Synthetic round | Terminus-2 | OpenHands | Source bytes match current Git index | Paid calls |
|---|---|---|---|---:|
| Initial | Verifier script could not execute | Verifier script could not execute | No | 0 |
| After LF verifier correction | Pass | Pass | No | 0 |
| Canonical staged Git bundle | Pass | Local action server connection failure; zero model requests | Yes | 0 |

The first round's verifier failure came from CRLF line endings in the deployed script. The second round passed but source fingerprints differed from Git bytes. A direct staged-blob bundle resolved that discrepancy. The current round binds all **277 Python sources** and the exact suffix manifest, but its OpenHands action server did not become reachable at its own localhost endpoint. This is runtime startup, not an OpenRouter request failure. No paid request or task was repeated.

**Current source is not qualified for paid execution.** Earlier synthetic passes cannot replace the failed current gate. See [current qualification](qualification-current.json) and [preparation audit](preparation-audit.json).

## Logs and spending

All three rounds' model exchanges, runtime output, verifier output, ledgers and controller logs remain private. **112 metadata observations across six synthetic traces** were exported to local Langfuse and read back by ID; synthetic observations are separate from benchmark scores. They contain thirteen synthetic generation observations and zero paid API generations. All fixture task containers were removed. Langfuse was restored at http://127.0.0.1:3300.

Confirmed experiment spending remains US$31.490725275; unresolved reserves remain US$2.20. The conservative allowance under the US$50 cap remains US$16.309274725, subject to live credit. A read-only billing lookup on 12 October Sydney still returned HTTP 404 for the new unknown charge; no closed ledger was modified.

## Model identity and next direction

Google's [release notes](https://ai.google.dev/gemini-api/docs/changelog) state that the generic Gemini 3.7 Flash model was deprecated on 8 October and requests are rerouted to 3.8. OpenRouter's public [endpoint metadata](https://openrouter.ai/api/v1/models/google/gemini-3.7-flash/endpoints) still names the dated `google/gemini-3.7-flash-20260813` Google AI Studio endpoint with the expected limits and prices. These sources leave actual version continuity unresolved; metadata alone does not prove which model is served. See [endpoint recheck](model-endpoint-recheck.json).

The original twenty custom attempts and eighteen native attempts remain immutable. The full native comparison is incomplete. The user's direction is pending after their statement that the group has selected DeepSeek V4: focus on the completed DeepSeek results, or continue the Gemini suffix under the existing cap after current qualification and fixed-version requirements are satisfied.
