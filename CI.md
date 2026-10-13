# CI

The scaffold CI currently checks:

- installability with `uv`
- linting with `ruff`
- formatting with `ruff format --check`
- type checking with `mypy`
- tests with `pytest`
- package build integrity with `python -m build` and `twine check`

The workflows live under [`.github/workflows/`](.github/workflows/).

For the human pre-release flow around those checks, see
[`PRE_RELEASE.md`](PRE_RELEASE.md).

## v0.4 controlled configuration

See [configuration and approvals](docs/configuration.md) for Tower ownership, action lifecycle, audit durability and API/CLI usage.
Runtime settings remain mirrored or unsupported without an adapter.

Wheel and sdist use core metadata 2.4 for compatibility with the locked
Python 3.10-compatible Twine verifier.

## v0.5 evidence posture

`make check` covers evidence storage, posture, HTTP/CLI, snapshot and example
tests. `make test-ecosystem` also runs the optional actual-producer reader tests
against local sibling checkouts. Console DOM checks run separately with Node
(see README).
