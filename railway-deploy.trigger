# Railway production deploy trigger

Railway production auto-deploys are gated by `railway.toml` so this file is the
only watched path. Bump this file only after the Railway Dockerfile contract and
healthcheck contract have been reviewed.

Last intentional production promotion: 2026-06-02 after restoring deployment
guardrails for fork/upstream sync safety.