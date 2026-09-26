# Repository workflow

- Work on `main` and push approved project changes to `origin/main`, unless the user explicitly requests another branch. Fetch and inspect the remote before pushing; do not overwrite new remote work.
- Use the repository's configured GitHub-linked author identity. Preserve original benchmark commit IDs and authorship unless a separate history change is explicitly authorised.
- Write short, factual commit messages that describe the actual change. Avoid hype, generic filler, unsupported success claims and empty commits.
- Stage files explicitly. Do not commit credentials, raw model exchanges, private archives, PDFs or unrelated local work.
- Keep other contributors' branches and recovery branches intact. Do not merge their work back into `main` without authorisation.
- Run the checks affected by a change. Label synthetic setup checks separately from paid-provider tests and benchmark scores.
