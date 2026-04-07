"""evaluation package"""
from .engine               import evaluate, EvaluationResult, WorkoutSuggestion, CategoryResult
from .progressive_overload import analyse_overload, OverloadResult
from .split_detector       import analyse_split, SplitResult
from .recovery_analysis    import analyse_recovery, RecoveryResult
from .edge_cases           import detect_edge_cases, EdgeCaseResult

__all__ = [
    "evaluate", "EvaluationResult", "WorkoutSuggestion", "CategoryResult",
    "analyse_overload", "OverloadResult",
    "analyse_split", "SplitResult",
    "analyse_recovery", "RecoveryResult",
    "detect_edge_cases", "EdgeCaseResult",
]