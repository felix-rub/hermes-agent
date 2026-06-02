# felix-rub Railway upstream sync

This fork deploys directly to Railway and must stay close to
`NousResearch/hermes-agent` while preserving the small Docker runtime changes
Railway needs.

## Production auto-deploy gate

This fork tracks a fast-moving public upstream, but the Railway production
service needs fork-specific deployment invariants:

- no Docker `VOLUME ["/opt/data"]` declaration;
- dashboard auth bypass for the public Railway bind via `--insecure`;
- a listener on Railway's injected `$PORT` for healthchecks;
- a listener on the existing public domain target port `9119`.

Do not let normal upstream-sync pushes deploy production directly. The Railway
service may keep **Auto deploys when pushed to GitHub** enabled, but
`railway.toml` gates it with:

```toml
watchPatterns = ["railway-deploy.trigger"]
```

That means upstream merges, dependency bumps, and experimental branch syncs do
not deploy production unless `railway-deploy.trigger` changes too.

Production promotion checklist:

1. Apply or verify the Railway Dockerfile patch:
   `py scripts/apply_railway_docker_patch.py --check Dockerfile`
2. Run the Railway contract tests:
   `py -m py_compile scripts\apply_railway_docker_patch.py tests\scripts\test_apply_railway_docker_patch.py`
3. Update `railway-deploy.trigger` in the promotion commit.
4. Push the reviewed commit to the branch Railway watches, or deploy explicitly
   with `railway up --service hermes-agent --environment production`.
5. Verify `https://hermes-agent-production-cd90.up.railway.app/api/status` and
   `/` return HTTP 200.

Longer term, the safest construction is a dedicated production branch or an
image-based Railway service fed by CI after tests pass. The current trigger-file
gate is the minimal repo-level safety catch for the existing GitHub auto-deploy
setup.

## Repository roles

| Repository | Role |
| --- | --- |
| `NousResearch/hermes-agent` | Open-source upstream. Source of normal Hermes updates. |
| `felix-rub/hermes-agent` | Deployable fork. Railway builds from this repo. |
| `Fefe-GmbH/Hermes-Agent` | Private companion/brain repo: company-system, project files, custom skills. Not a fork of Hermes source. |

`Fefe-GmbH/Hermes-Agent` has no common Git ancestor with Hermes upstream and does
not contain the Hermes source directories (`agent/`, `hermes_cli/`, `gateway/`,
`tools/`, `ui-tui/`, `web/`, or `Dockerfile`). Do not use it as a source for
upstream syncs.

## Preserved Railway contract

Compared with upstream, this fork intentionally keeps two Dockerfile behaviors:

1. No Docker-managed anonymous volume for `/opt/data`:
   - remove `VOLUME [ "/opt/data" ]`
2. Two dashboard listeners for Railway's split routing behavior:
   - `HERMES_DASHBOARD=1`
   - `HERMES_DASHBOARD_HOST=0.0.0.0`
   - `HERMES_DASHBOARD_PORT=9119`
   - `HERMES_DASHBOARD_INSECURE=1`
   - the s6-supervised dashboard serves the existing public service-domain
      target port `9119`
   - the foreground `CMD` dashboard serves Railway's injected `$PORT` for
      `/api/status` healthchecks

The current upstream Docker image uses `s6-overlay`. Railway's generated domain
for this service targets port `9119`, while Railway healthchecks probe the
injected runtime `$PORT` (observed as `8080`). Running only the foreground
dashboard on `$PORT` made healthchecks pass but left the public route on `9119`
returning `502 Bad Gateway`; running only the s6 dashboard on `9119` fixed the
public route but failed Railway healthchecks. The fork therefore serves both
ports: s6 dashboard on `9119`, foreground dashboard on `$PORT`.

`railway.toml` is part of the same contract. It forces Railway to build via the
root `Dockerfile`, keeps the main foreground dashboard command on `$PORT`, probes
`/api/status`, and restarts on failure. This keeps Railway from reporting a
deploy as "running" when no HTTP dashboard is actually reachable.

## Automation

Automation lives in:

- `.github/workflows/sync-upstream-railway.yml`
- `railway.toml`
- `scripts/apply_railway_docker_patch.py`
- `tests/scripts/test_apply_railway_docker_patch.py`

The workflow runs daily and can also be started manually from GitHub Actions.

Flow:

1. Checkout `felix-rub/hermes-agent:main` with full history.
2. Fetch `NousResearch/hermes-agent:main` as `upstream/main`.
3. If upstream is already contained, only verify the Railway Docker contract.
4. Otherwise merge `upstream/main` into the fork with a normal merge commit.
5. If the merge conflicts:
   - auto-resolve only when the only conflicted file is `Dockerfile`
   - take upstream's Dockerfile as the base
   - re-apply the Railway contract with `scripts/apply_railway_docker_patch.py`
   - commit the merge
6. If any non-Dockerfile conflict appears, stop and fail the workflow.
7. Validate:
   - Railway patch check passes
   - `git diff --check` passes
8. Push the updated branch back to `main`.

No force-push is used. The original Railway commits remain in history.

## Manual trigger

Use GitHub Actions:

1. Open `felix-rub/hermes-agent`.
2. Go to **Actions**.
3. Select **Sync upstream and preserve Railway**.
4. Click **Run workflow** on `main`.

## Local verification

From a checkout of `felix-rub/hermes-agent`:

```bash
python scripts/apply_railway_docker_patch.py --check Dockerfile
git diff --check
git rev-list --left-right --count origin/main...upstream/main
```

Expected after a successful sync:

- the Railway patch check prints `already patched`
- `git diff --check` exits successfully
- `railway.toml` keeps `builder = "DOCKERFILE"`, `/api/status` healthchecks, and
   the foreground dashboard start command on `${PORT:-9119}`
- `origin/main...upstream/main` shows `0` on the upstream-behind side, unless
  upstream published new commits after the last sync

## Failure handling

### Workflow fails with a non-Dockerfile conflict

This means upstream changed files that overlap with fork-local changes outside
the known Railway Docker contract.

Fix manually:

1. Create a local branch from `origin/main`.
2. Fetch upstream.
3. Merge `upstream/main`.
4. Resolve conflicts intentionally.
5. Run `python scripts/apply_railway_docker_patch.py --check Dockerfile`.
6. Run `git diff --check`.
7. Push normally. Do not force-push.

### Workflow fails because the Railway patch check changed the file

Run:

```bash
python scripts/apply_railway_docker_patch.py Dockerfile
git diff -- Dockerfile
```

If the diff is only the expected `/opt/data` volume removal, Railway dashboard
environment variables, and Railway dashboard `CMD`, commit it.

### Railway deploy breaks after upstream Docker changes

Inspect upstream's new Docker runtime first. Keep upstream's architecture where
possible, then update `scripts/apply_railway_docker_patch.py` so the Railway
contract is expressed as a small, repeatable patch.

## Guardrails

- Keep fork-specific behavior small and documented here.
- Do not copy files from `Fefe-GmbH/Hermes-Agent` into this repo unless that is a
  deliberate product decision.
- Do not use force-push for upstream syncs.
- Do not replace upstream Docker architecture wholesale; patch only the Railway
   deployment contract: no Docker `VOLUME`, s6 dashboard on `9119`, foreground
   dashboard on `$PORT`.
