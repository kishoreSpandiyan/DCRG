"""
Simulation Engine Module for DCRG Phase 7.
Exports RobotSimulator, SimulationManager, schemas, and global singleton.
"""

from app.modules.simulation_engine.schemas import (
    CommandExecutionRecord,
    ExecutionResultType,
    Obstacle,
    RobotPose,
    SimulationConfig,
    SimulationControlRequest,
    SimulationState,
)
from app.modules.simulation_engine.simulator import RobotSimulator
from app.modules.simulation_engine.manager import SimulationManager, simulation_manager

__all__ = [
    "CommandExecutionRecord",
    "ExecutionResultType",
    "Obstacle",
    "RobotPose",
    "SimulationConfig",
    "SimulationControlRequest",
    "SimulationState",
    "RobotSimulator",
    "SimulationManager",
    "simulation_manager",
]

