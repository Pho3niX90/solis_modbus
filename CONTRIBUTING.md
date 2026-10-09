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

Releases are cut from a `release/X.Y.Z` branch:

1. **Cut the branch** from master, e.g. `release/4.4.0`. This creates (or reopens) milestone `4.4.0` and publishes release candidate `v4.4.0-rc.1`.
2. **Assign issues** that will ship in this version to the milestone.
3. **Open PRs against the release branch.** Each merge adds the PR to the milestone and publishes the next candidate (`v4.4.0-rc.2`, ...) as a GitHub pre-release. A push that changes nothing under `custom_components/` publishes nothing. In HACS, enable *Show beta versions* for this repository to install candidates.
4. **Cut the release**: run the *Release* workflow on the release branch with `release_type=release`. It publishes `v4.4.0` as the latest release, opens a PR merging the branch back into master (listing the milestone's open issues as `Closes #N`; remove any that aren't fixed), and closes the milestone.
5. **Merge the back-merge PR.** This opens the next release branch (`release/4.5.0`), which creates its milestone. Its first candidate is published once it differs from the last release.

Candidates stamp `X.Y.Z-rc.N` into `manifest.json` in a commit only their tag points to, so the branch carries no version-bump commits until the final release.

Running *Release* on master still works as before for hotfixes (it bumps the patch version).
