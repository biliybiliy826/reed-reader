# Reed Reader / 苇读

Linux native reader, independent implementation inspired by publicly documented Fish-book features.

- Map: `docs/README.md`; architecture: `docs/architecture.md`.
- Active work: `docs/packaging-plan.md`; WeRead verification: `docs/weread-plan.md`; original foundation: `docs/implementation-plan.md`.
- Runtime: `src/reed_reader/app.py`; start with `uv run reed-reader`.
- Validate: `QT_QPA_PLATFORM=offscreen uv run pytest`; `uv run ruff check .`.
- Local state lives in XDG_DATA_HOME/reed-reader, never in the repository.
- GUI/SQLite ownership stays on the Qt main thread; workers return immutable results.
- Never copy proprietary Fish-book code, branding, artwork, or bundled books.
- Network access is limited to the explicitly configured Legado service and the user-opened WeRead official web window; no bundled book sources.
- WeRead uses its own WebEngine profile. Never extract account cookies or book content into the local library; navigation and permissions stay with the official site.
- Keep Linux/Wayland capability limits and tested vs untested features explicit.
