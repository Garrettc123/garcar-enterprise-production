# Vendored copy of `/approval_gate` (GAR-530)

`render.yaml` deploys the backend with `rootDir: backend`, so the backend cannot rely on
the repo-root package being importable. This directory is a byte-for-byte copy of
`/approval_gate/*.py`. `tests/test_approval_gate.py::test_backend_copy_is_identical`
fails if the two drift. Edit `/approval_gate/` and re-copy:

    cp approval_gate/*.py backend/approval_gate/
