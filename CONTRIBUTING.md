# Contributing Guidelines

## Local development

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) tool.
2. Install project dependencies using `uv sync` command.

## Code style

Check code style:

```bash
uv run ruff check
```


## Code formatting

Format code:

```bash
uv run ruff format
```

## Testing

Run all tests:

```bash
uv run pytest
```

Run a single test:

```bash
uv run pytest tests/test_services.py
```

## Releases

Master is the trunk: **open PRs against master**. Each version is released from a `release/X.Y.0` branch that follows master:

1. **The branch is opened** when the previous release is merged back (or cut by hand, e.g. `release/4.4.0` from master). This creates (or reopens) milestone `4.4.0` and publishes release candidate `v4.4.0-rc.1` once there is something new since the last release.
2. **Assign issues** that will ship in this version to the milestone.
3. **Merge PRs into master.** Every push to master is merged into each open `release/X.Y.0` branch, which publishes the next candidate (`v4.4.0-rc.2`, ...) as a GitHub pre-release, and the merged PR is added to the milestone of the lowest open release. If that merge conflicts, a `sync/master-into-4.4.0` PR is opened; resolve the conflicts there. In HACS, enable *Show beta versions* for this repository to install candidates.
4. **Cut the release**: run the *Release* workflow on the release branch with `release_type=release`. It publishes `v4.4.0` as the latest release, opens a PR merging the branch back into master (listing the milestone's open issues as `Closes #N`; remove any that aren't fixed), and closes the milestone.
5. **Merge the back-merge PR.** This opens `release/4.5.0`, and the cycle repeats.

Fixes meant only for the release can be PR'd straight to the release branch; the back-merge brings them to master. Candidates stamp `X.Y.Z-rc.N` into `manifest.json` in a commit only their tag points to, so the branch carries no version-bump commits until the final release. A push that changes nothing under `custom_components/` publishes no candidate.

**Major versions.** Breaking work for the next major goes straight to its branch, e.g. `release/5.0.0`, not master (or it would ship in 4.x). That branch still receives every master push, so 4.x fixes reach it; a conflicting merge opens a `sync/master-into-5.0.0` PR. Once 5.0.0 is released and merged back, open 4.x branches can no longer be released; the merged PR gets a comment naming them.

**Hotfixes.** Master may hold unreleased features, so cut a hotfix from the last release tag instead: `git push origin v4.4.0:refs/heads/release/4.4.1`, then PR the fix against that branch. It gets candidates and a milestone like any release branch but doesn't receive master. Release it, then merge it back. Running *Release* on master still works, but warns while release branches are open.
