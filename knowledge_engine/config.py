"""Application configuration.

Configuration is intentionally small in Phase 0. Keeping it in one object makes it
straightforward to add environment-specific settings later without global state.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for Knowledge Engine Core."""

    project_root: Path = Field(default_factory=lambda: Path.cwd())
    data_dir: Path | None = None
    database_url: str | None = None
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="KE_", env_file=".env", extra="ignore")

    @property
    def resolved_data_dir(self) -> Path:
        """Return the data directory, defaulting under the project root."""

        return self.data_dir or self.project_root / "data"

    @property
    def resolved_database_url(self) -> str:
        """Return the SQLAlchemy database URL."""

        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.resolved_data_dir / 'knowledge_engine.sqlite3'}"


def build_settings(project_root: Path | None = None) -> Settings:
    """Create settings for a command invocation."""

    if project_root is None:
        return Settings()
    return Settings(project_root=project_root)
