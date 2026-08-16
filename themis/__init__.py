"""Stable public surface for integrating with Themis.

Implementation modules remain under :mod:`src` for compatibility. New research
code should import from :mod:`themis` and its documented submodules.
"""

from src.version import __version__

__all__ = ["__version__"]
