# Reed Reader / 苇读

Linux native reader, independent implementation inspired by publicly documented Fish-book features.

- Map: `docs/README.md`; architecture: `docs/architecture.md`.
- Active work and verification: `docs/implementation-plan.md`.
- Runtime: `src/reed_reader/app.py`; start with `uv run reed-reader`.
- Validate: `QT_QPA_PLATFORM=offscreen uv run pytest`; `uv run ruff check .`.
- Local state lives in XDG_DATA_HOME/reed-reader, never in the repository.
- GUI/SQLite ownership stays on the Qt main thread; workers return immutable results.
- Never copy proprietary Fish-book code, branding, artwork, or bundled books.
- Network requests only target the explicitly configured Legado service; no bundled sources.
- Keep Linux/Wayland capability limits and tested vs untested features explicit.
