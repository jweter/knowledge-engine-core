"""Knowledge Engine Core.

Phase 0 provides offline ingestion and search for scientific PDFs.
"""

import time

# Captured at the earliest point this process's own code can observe --
# `knowledge_engine` package import, which happens before any of its
# submodules (typer, sqlalchemy, rich, and the `ke` command surface itself)
# are imported. Used by `process_startup_timing.py` (issue #433 item 1) to
# measure `ke`'s own fixed per-invocation startup cost, separate from a
# command's retrieval/search/acquisition work. This does not include the
# Python interpreter's own startup before it began importing this package.
_PACKAGE_IMPORT_MONOTONIC = time.monotonic()

__all__ = ["__version__"]

__version__ = "0.1.0"
