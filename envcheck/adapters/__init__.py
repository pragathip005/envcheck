"""Translates each environment format (verifiers, tau-bench, custom-JSON, ...)
into the standard envcheck.core.types.Task shape. This is the only layer that
should ever need to know environment-format-specific details.
"""
