"""
DCRG Fusion Engine Module for Phase 5.
Multi-factor Cross-Reliability Score (CRS) generation,
temporal alignment decay, and zero-override contradiction veto filter.
"""

from app.modules.fusion_engine.schemas import (
    AnalyticalFinding,
    CRSStatus,
    FusionConfig,
    FusionEngineStatus,
    FusionFactors,
    FusionResult,
)
from app.modules.fusion_engine.calculator import CRSCalculator
from app.modules.fusion_engine.manager import FusionManager, fusion_manager

__all__ = [
    "AnalyticalFinding",
    "CRSStatus",
    "FusionConfig",
    "FusionEngineStatus",
    "FusionFactors",
    "FusionResult",
    "CRSCalculator",
    "FusionManager",
    "fusion_manager",
]
