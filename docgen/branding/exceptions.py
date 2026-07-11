# coding: utf-8
"""
exceptions.py -- Exception hierarchy for the Turn2Law Branding Engine.
"""


class BrandingEngineError(Exception):
    """Base class for all Branding Engine exceptions."""


class BrandProfileError(BrandingEngineError):
    """Raised for invalid profile configuration, invalid mode, or tampered preamble."""


class BrandAssetValidationError(BrandingEngineError):
    """Raised when a PNG asset fails format, dimension, or file-size validation."""


class BrandAssetProcessingError(BrandingEngineError):
    """Raised when Pillow cannot process (trim/save) an image asset."""


class BrandProfileNotFoundError(BrandingEngineError):
    """Raised when a requested profile_id does not exist in the Profiles Store."""
