"""Whitelist for Vulture false positives (dynamic imports, DI, re-exports).

Add symbols here only when Vulture reports them incorrectly. Prefer fixing
code or tightening scope over growing this file. See docs/Develop/dead-code-pipeline.md.
"""

# Example pattern (uncomment and adapt when needed):
# from some.module import _KEEP_FOR_API  # noqa: Vulture may flag re-exports
