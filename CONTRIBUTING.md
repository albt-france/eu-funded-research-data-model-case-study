# Contributing

## Workflow

1. Create a branch from `main` named after the change: `feature/...`, `fix/...` or `docs/...`.
2. Keep commits small, with a message that says what changed and why (imperative mood: "Add ...", "Fix ...").
3. Run `pytest` before pushing. CI runs the tests and applies the DDL to a PostgreSQL 16 server.
4. Open a pull request; merge with a merge commit (`--no-ff`) so that each feature stays readable in the history.
5. Releases are tagged (`v1.0`, ...).

## Rules

- A change to the model starts in `model/ddl/schema.sql`; then regenerate the dictionary (`python src/build_dictionary.py`)
  and update the Mermaid diagram in `model/diagrams/`.
- A new cleaning rule goes into `src/clean.py` with a unit test, and into the cleaning log if it changes rows.
- A new business rule is enforced by a constraint where the database allows it, otherwise by a check in `src/quality.py`.
- Numbers in documents are read from pipeline outputs, never typed by hand.
- No personal data, no secrets: settings go in a local `.env` (ignored by Git), see `.env.example`.
