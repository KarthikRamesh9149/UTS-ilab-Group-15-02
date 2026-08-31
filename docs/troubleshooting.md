# Troubleshooting

- If Docker reports a missing `docker-credential-desktop`, source `scripts/lib.sh` so the project-isolated Docker configuration is used.
- If Harbor reports `unknown flag: --project-name`, install the Docker Compose plugin and confirm `docker compose version` works.
- If containers cannot reach Ollama, confirm the server is bound to `0.0.0.0:11434`, then run `make model-test`.
- Do not retry a completed reward-zero agent trial. Only retry an unambiguous setup, image-pull, container-start, or model-connection failure, at most twice.

