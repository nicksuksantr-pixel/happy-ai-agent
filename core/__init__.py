"""HAPPY AI Agent — `core` package.

Cross-cutting infrastructure that has no dependency on `ui`:
- `config`     — paths, frozen-aware resolution, version, constants.
- `persistence` — JSON helpers for window state, settings, etc.

Backend modules (auth, pipeline, agents, builder, updater, extractor,
file_loader) live at the project root and remain untouched — they
predate this restructure and the spec already lists them.
"""
