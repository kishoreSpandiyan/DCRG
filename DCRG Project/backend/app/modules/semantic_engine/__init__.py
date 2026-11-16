"""
Semantic Engine Module (Phase 3).
Maps spoken transcripts to canonical robot primitives with confidence scoring.
"""

from app.modules.semantic_engine.classifier import (
    SemanticClassifier,
    SemanticClassificationResult,
    semantic_classifier,
)

__all__ = [
    "SemanticClassifier",
    "SemanticClassificationResult",
    "semantic_classifier",
]
