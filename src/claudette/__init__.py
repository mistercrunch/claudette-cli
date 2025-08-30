"""Claudette - Superset multi-environment workflow manager."""

try:
    from ._version import __version__
except ImportError:
    # Fallback version if _version.py doesn't exist (development mode)
    __version__ = "development"
