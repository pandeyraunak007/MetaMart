"""Importing this package triggers registration of every built-in rule."""
from metamart.quality.rules import (  # noqa: F401
    datatypes,
    glossary,
    lineage,
    naming,
    normalization,
    orphans,
    pks,
)
