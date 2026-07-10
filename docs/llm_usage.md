# LLM And Agent Usage

This document describes how AI-assisted coding was used for the Claude Code telemetry analytics platform. It is intended to make the agent setup reproducible and to clarify which parts of the solution were generated, reviewed, and verified.

## AI Coding Tool Used

The project was developed with OpenAI Codex as the AI coding agent. Codex operated in the local repository, read the project instructions, edited files, ran commands, and iterated based on test and runtime feedback.

The committed setup used by Codex is part of the deliverable:

- [AGENTS.md](../AGENTS.md)
- [.codex/skills/telemetry-analysis/SKILL.md](../.codex/skills/telemetry-analysis/SKILL.md)

## How `AGENTS.md` Guides The Project

[AGENTS.md](../AGENTS.md) is the root project contract. It defines:

- the assignment goal,
- the source dataset structure,
- the nested JSONL parsing rules,
- the normalized data model,
- expected metric categories,
- coding conventions,
- testing expectations,
- reproducible commands.

The most important constraint from `AGENTS.md` is that `telemetry_logs.jsonl` lines are batches. The parser must parse each line, iterate `batch["logEvents"]`, then parse each log event's `message` field as a second JSON object. The app, tests, schema, and README all follow that contract.

## How The `telemetry-analysis` Skill Helps

The custom [telemetry-analysis skill](../.codex/skills/telemetry-analysis/SKILL.md) gives dataset-specific guidance to the agent. It repeats and expands the data contract in operational form:

- known event bodies,
- common and event-specific fields,
- normalized table names,
- type coercion rules,
- dashboard personas,
- metric definitions and denominators,
- validation and testing expectations.

This prevented generic JSONL assumptions and kept the implementation focused on the assignment-specific telemetry shape.

## AI-Assisted Parts Of The Solution

Codex assisted with implementation across the repository, including:

- project scaffold and command setup,
- sample and realistic data generation commands,
- nested JSONL parser,
- event normalizer and type coercion,
- validation and quarantine behavior,
- employee CSV loading and enrichment checks,
- DuckDB schema and ingestion writer,
- metric/query layer,
- Streamlit dashboard with filters,
- deterministic test fixtures,
- parser, validation, storage, metrics, and dashboard-supporting tests,
- README and architecture documentation.

The generated code was not treated as final by default. It was reviewed through command output, tests, sample data runs, schema checks, and dashboard startup checks.

## Manual Review And Verification

The implementation was manually checked against the project contract in these ways:

- verified `AGENTS.md` and the skill before each implementation step,
- compared parser behavior against the nested JSONL shape,
- inspected generated files and row counts after data generation,
- verified DuckDB table creation and row counts,
- checked that metrics use explicit denominators,
- confirmed dashboard charts are backed by metric functions,
- reviewed README commands against the Makefile,
- ran the deterministic test suite.

Primary verification commands:

```bash
make test
python3 -m compileall app src tests
make demo-data
```

The Streamlit dashboard was also started locally with:

```bash
make demo
```

or:

```bash
make dev
```

## Reproducing The Agent Setup

To reproduce the setup in this repository:

1. Use an agentic coding tool that reads repository instructions, such as OpenAI Codex.
2. Keep [AGENTS.md](../AGENTS.md) at the repository root.
3. Keep the custom skill at [.codex/skills/telemetry-analysis/SKILL.md](../.codex/skills/telemetry-analysis/SKILL.md).
4. Instruct the agent to use both the root agent instructions and the `$telemetry-analysis` skill.
5. Install project dependencies:

```bash
make install-deps
```

6. Run the demo:

```bash
make demo
```

Validate the skill definition with:

```bash
python3 /Users/oscarsegura/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/telemetry-analysis
```

That validation command depends on the local Codex skill validator path used during development. If another environment uses a different Codex home directory, adjust the validator path accordingly.

## Secrets And API Keys

No secrets, API keys, or external service credentials are required for this project.

The data generator creates synthetic telemetry and employee records locally. The application uses local files and a local DuckDB database:

- `data/sample`
- `data/raw`
- `data/processed/telemetry.duckdb`

Generated data and local database files are ignored by Git. `.env.example` contains only non-secret local path defaults.

## Known Limitations Of AI-Generated Assistance

AI assistance accelerated implementation, but it has limitations:

- It can make incorrect assumptions if the nested telemetry contract is not explicitly enforced.
- It can produce plausible metric names without correct denominators unless tests and reviews check them.
- It may overfit tests to small fixtures if realistic sample runs are not also checked.
- It can miss operational edge cases such as large-file performance, deployment packaging, and concurrent use.
- It cannot replace ownership of the solution; the final architecture, code behavior, and tradeoffs still need human understanding and review.

For this reason, the repository includes deterministic fixtures, validation tests, DuckDB row-count checks, and documentation tying claims back to implemented code and commands.
