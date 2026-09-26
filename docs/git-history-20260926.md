# Git history update, 26 September 2026

At the owner's request, `main` now contains the project's 138 owner-authored commits. Three collaborator commits were removed from its ancestry; their code remains on the original collaborator and recovery branches.

The email on 75 commits was corrected to the owner's GitHub-linked address. Author and committer names, dates, messages and every file tree were preserved. Descendant commit IDs changed too. GitHub's API confirmed that all 138 commits on the repaired history resolve to `KarthikRamesh9149`.

Recovery branches:

- `backup/main-before-owner-sync-20260926`: the previous shared main, at `a5f3e9d95adb389d243bd77420fe011b52cba0be`.
- `backup/main-before-author-fix-20260926`: the original project history, at `da9b4a8a58f89465f6eb8850081252e08be0e0cf`.

Other branches were not changed. Recorded experiment source IDs deliberately remain the original IDs: their objects are retained in the recovery branch and original study branches. No server source, result or qualification was rewritten by this Git metadata change.

| Checkpoint | Original ID retained for provenance | Equivalent ID on main |
|---|---|---|
| Corrected baseline results | `2d0ad578991c48d5ef46526a231dd2e41f28a94e` | `dc2ec7c61b6cec33622a89b9b4e09579fb900dbc` |
| Diagnostic implementation | `c216ae26d25bbaa45fdb00d1ac50d37fe5754ad9` | `f377cb94a9a71e94b19490632a920b7982180273` |
| Diagnostic results | `dfb9d7092e10393c1dc98332b684f849dbc299b1` | `98fff550088628a471470441c7d62dc93b0d4b15` |
| Custom runtime | `da9b4a8a58f89465f6eb8850081252e08be0e0cf` | `efdfa5b3a523cecdcc3d9522b59ce37f6efb318f` |

New work is committed to `main` with the GitHub-linked identity and short factual messages. Unrelated local PDFs, private archives, credentials and raw experiment logs are excluded.
