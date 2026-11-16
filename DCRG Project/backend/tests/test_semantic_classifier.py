"""
Automated unit tests for Semantic Command Classification (Phase 3).
Verifies mapping, edge cases, ambiguity detection, low-confidence handling,
and safety invariants (e.g. STOP override, shouting STOP not rejected).
"""

import pytest
from app.modules.voice_engine.schemas import (
    CanonicalCommand,
    SemanticStatus,
)
from app.modules.semantic_engine.classifier import SemanticClassifier


@pytest.fixture
def classifier():
    return SemanticClassifier(
        recognition_confidence_threshold=0.60,
        classification_confidence_threshold=0.70,
    )


class TestCanonicalCommandMappings:
    """Test mapping of standard operational utterances to canonical commands."""

    @pytest.mark.parametrize("phrase", [
        "left",
        "move left",
        "turn left",
        "steer left",
        "rotate left",
        "step left",
        "go left",
    ])
    def test_left_classification(self, classifier, phrase):
        result = classifier.classify(phrase, recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.LEFT
        assert result.semantic_status == SemanticStatus.VALID
        assert result.direction_vector == {"x": -1.0, "y": 0.0}
        assert result.classification_confidence >= 0.70

    @pytest.mark.parametrize("phrase", [
        "right",
        "turn right",
        "move right",
        "steer right",
        "rotate right",
        "go right",
    ])
    def test_right_classification(self, classifier, phrase):
        result = classifier.classify(phrase, recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.RIGHT
        assert result.semantic_status == SemanticStatus.VALID
        assert result.direction_vector == {"x": 1.0, "y": 0.0}
        assert result.classification_confidence >= 0.70

    @pytest.mark.parametrize("phrase", [
        "forward",
        "move forward",
        "go forward",
        "ahead",
        "straight",
        "go straight",
        "advance",
    ])
    def test_forward_classification(self, classifier, phrase):
        result = classifier.classify(phrase, recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.FORWARD
        assert result.semantic_status == SemanticStatus.VALID
        assert result.direction_vector == {"x": 0.0, "y": 1.0}
        assert result.classification_confidence >= 0.70

    @pytest.mark.parametrize("phrase", [
        "backward",
        "move backward",
        "move backwards",
        "back up",
        "reverse",
        "go back",
    ])
    def test_backward_classification(self, classifier, phrase):
        result = classifier.classify(phrase, recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.BACKWARD
        assert result.semantic_status == SemanticStatus.VALID
        assert result.direction_vector == {"x": 0.0, "y": -1.0}
        assert result.classification_confidence >= 0.70

    @pytest.mark.parametrize("phrase", [
        "stop",
        "halt",
        "freeze",
        "don't move",
        "dont move",
        "do not move",
        "hold position",
        "emergency stop",
        "abort",
    ])
    def test_stop_classification(self, classifier, phrase):
        result = classifier.classify(phrase, recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.STOP
        assert result.semantic_status == SemanticStatus.VALID
        assert result.direction_vector == {"x": 0.0, "y": 0.0}
        assert result.classification_confidence >= 0.90


class TestSafetyInvariantsAndAmbiguity:
    """Tests critical safety guardrails for speech classification."""

    def test_stop_override_on_compound_phrase(self, classifier):
        """STOP must override directional words in emergency phrases."""
        # E.g. "stop moving left" contains "stop" and "left"
        result = classifier.classify("stop moving left", recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.STOP
        assert result.semantic_status == SemanticStatus.VALID

    def test_dont_move_maps_to_stop(self, classifier):
        result = classifier.classify("don't move", recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.STOP
        assert result.semantic_status == SemanticStatus.VALID

    def test_conflicting_directions_yield_uncertain(self, classifier):
        """Contradictory directional primitives must result in UNCERTAIN, not guessing."""
        result = classifier.classify("move left and right", recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.UNCERTAIN
        assert result.semantic_status == SemanticStatus.UNCERTAIN

    def test_low_recognition_confidence_yields_uncertain(self, classifier):
        """Speech below configured STT threshold must be tagged UNCERTAIN, never guessed."""
        # STT recognized "move forward" but confidence is only 0.45 (< 0.60 threshold)
        result = classifier.classify("move forward", recognition_confidence=0.45)
        assert result.recognized_command == CanonicalCommand.UNCERTAIN
        assert result.semantic_status == SemanticStatus.UNCERTAIN

    def test_unsupported_speech_yields_unknown(self, classifier):
        """Out-of-vocabulary utterances must yield UNKNOWN with non-actionable zero vector."""
        result = classifier.classify("what is the weather today", recognition_confidence=0.95)
        assert result.recognized_command == CanonicalCommand.UNKNOWN
        assert result.semantic_status == SemanticStatus.UNKNOWN
        assert result.direction_vector == {"x": 0.0, "y": 0.0}

    def test_empty_transcript_yields_unknown(self, classifier):
        result = classifier.classify("", recognition_confidence=0.0)
        assert result.recognized_command == CanonicalCommand.UNKNOWN
        assert result.semantic_status == SemanticStatus.UNKNOWN

    def test_tamil_extensibility(self, classifier):
        """Tamil phrases should classify correctly when language='ta'."""
        result_stop = classifier.classify("நிறுத்து", recognition_confidence=0.95, language="ta")
        assert result_stop.recognized_command == CanonicalCommand.STOP

        result_fwd = classifier.classify("முன்னாடி போ", recognition_confidence=0.95, language="ta")
        assert result_fwd.recognized_command == CanonicalCommand.FORWARD

