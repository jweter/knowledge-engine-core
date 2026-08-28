"""Composed entry point for the staged hosted Research Copilot runtime."""

from knowledge_engine.research_acquisition_surface import (
    register_research_oa_acquisition_commands,
)
from knowledge_engine.research_command_surface import (
    RESEARCH_RUNTIME_CONTRACT_VERSION,
    RESEARCH_RUNTIME_REQUIRED_COMMANDS,
    app,
    research_runtime_capability_payload,
)
from knowledge_engine.research_secondary_acquisition_surface import (
    register_research_secondary_acquisition_commands,
)

register_research_oa_acquisition_commands(app)
register_research_secondary_acquisition_commands(app)

__all__ = [
    "RESEARCH_RUNTIME_CONTRACT_VERSION",
    "RESEARCH_RUNTIME_REQUIRED_COMMANDS",
    "app",
    "research_runtime_capability_payload",
]
