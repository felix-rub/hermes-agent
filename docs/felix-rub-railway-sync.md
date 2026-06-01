# felix-rub Railway upstream sync

This fork deploys directly to Railway and must stay close to
`NousResearch/hermes-agent` while preserving the small Docker runtime changes
Railway needs.

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
2. A long-running default process for Railway:
   - enforce `CMD ["sleep", "infinity"]`

The current upstream Docker image uses `s6-overlay`. The Railway keepalive `CMD`
works with that setup because supervised services can run while the container's
main process stays alive.

## Automation

Automation lives in:

- `.github/workflows/sync-upstream-railway.yml`
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

If the diff is only the expected `/opt/data` volume removal and keepalive `CMD`,
commit it.

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
  deployment contract.
