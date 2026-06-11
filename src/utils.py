"""Utility helpers for DAIS Project."""


def format_status(name: str, version: str, module_count: int) -> str:
    """Format the project status message."""
    return f"{name} v{version} has {module_count} module(s) configured."
