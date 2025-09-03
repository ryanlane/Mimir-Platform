---
applyTo: "**"
---

# Project – General Coding Standards

These rules apply to all code in this repository (backend, scripts, infra, docs). Prefer clarity over cleverness.

## Naming & Structure
- **PascalCase** for classes and types; **snake_case** for files, variables, functions; **SCREAMING_SNAKE_CASE** for constants.
- Keep file names short and descriptive: `user_service.py`, `image_utils.py`.
- One top-level concept per file. Favor folders over giant files.

## Source Layout & Dependencies
- Use **relative package imports** within the project (`from .services import user_service`).
- Prefer **standard library** first, then vetted deps. Keep dependencies minimal and pinned in `pyproject.toml`.
- Never commit secrets. Use `.env.example` to document required variables.

## Comments & Docs
- Write **why**, not what. Keep comments high-signal.
- Public modules, classes, and functions must have docstrings. Prefer **Google-style docstrings**.

## Error Handling & Logging
- Fail fast on programmer errors; handle expected operational errors explicitly.
- Always **log with context** (who/what/ids). Never log secrets or PII.
- Prefer structured logs (key=value) and consistent error messages.

## Tests & Quality Gates
- Write tests with **pytest**. New features require tests (unit where possible, integration where valuable).
- Keep tests fast; use fakes/mocks for external systems.
- Code must pass **formatting (Black)**, **linting (Ruff)**, and **type checks (mypy/pyright)**.

## Performance & Reliability
- Choose **O(n)** over clever micro-optimizations—measure before optimizing.
- Avoid needless global state. Prefer explicit dependency injection.

## Git & Reviews
- Small, atomic PRs with clear titles and descriptions.
- Commit messages: imperative mood (`Add X`, `Fix Y`). Reference issues.

## Security Baselines
- Validate all inputs; treat everything external as hostile.
- Principle of least privilege—for services, tokens, DB roles, and file permissions.
- Keep third-party libs updated; watch advisories.

## UI/UX (if applicable)
- Accessibility first: semantics, ARIA, focus order, color contrast.
- Consistent spacing/typography via tokens or variables.

> **Copilot hints:** Prefer readable code; avoid “magic.” Suggest typed functions, small modules, and explicit returns.
