from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .utils import read_json, write_json

DEFAULT_CONFIG_NAME = "paragraph_real_embedding"


@dataclass(frozen=True)
class RetrievalConfig:
    chunking_mode: str = "paragraph"
    chunk_overlap_pct: float = 0.15
    paragraph_min_chars: int = 120
    paragraph_max_chars: int = 800
    embedding_backend: str = "sentence_transformer"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    fusion_strategy: str = "weighted"
    weighted_alpha: float = 0.7
    weighted_beta: float = 0.3
    rrf_k: int = 60

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RetrievalConfig":
        return cls(**payload)


CONFIG_PRESETS: dict[str, RetrievalConfig] = {
    "baseline_current": RetrievalConfig(
        chunking_mode="fixed",
        embedding_backend="hash",
        fusion_strategy="weighted",
    ),
    "paragraph_only": RetrievalConfig(
        chunking_mode="paragraph",
        embedding_backend="hash",
        fusion_strategy="weighted",
    ),
    "paragraph_rrf": RetrievalConfig(
        chunking_mode="paragraph",
        embedding_backend="hash",
        fusion_strategy="rrf",
    ),
    "paragraph_real_embedding": RetrievalConfig(
        chunking_mode="paragraph",
        embedding_backend="sentence_transformer",
        fusion_strategy="weighted",
    ),
    "paragraph_real_embedding_rrf": RetrievalConfig(
        chunking_mode="paragraph",
        embedding_backend="sentence_transformer",
        fusion_strategy="rrf",
    ),
}


def save_index_config(path: Path, config: RetrievalConfig) -> None:
    write_json(path, config.to_dict())


def load_index_config(path: Path) -> RetrievalConfig:
    if not path.exists():
        return RetrievalConfig()
    return RetrievalConfig.from_dict(read_json(path))
