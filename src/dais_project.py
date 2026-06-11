"""Core DAIS Project implementation."""

from dataclasses import dataclass, field
from typing import List

from .utils import format_status


@dataclass
class DAISProject:
    name: str
    version: str = "0.1.0"
    modules: List[str] = field(default_factory=list)

    def add_module(self, module_name: str) -> None:
        """Add a module to the DAIS project."""
        if module_name not in self.modules:
            self.modules.append(module_name)

    def remove_module(self, module_name: str) -> None:
        """Remove a module from the DAIS project."""
        if module_name in self.modules:
            self.modules.remove(module_name)

    def status(self) -> str:
        """Return a formatted status string for the project."""
        return format_status(self.name, self.version, len(self.modules))
