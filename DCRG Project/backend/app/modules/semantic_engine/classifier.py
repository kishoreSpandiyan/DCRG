"""
Dedicated Semantic Command Classifier for DCRG Voice Engine.
Maps operator spoken transcripts to canonical robot primitives with confidence scoring
and defensive ambiguity rejection.
"""

import re
import string
import time
from typing import Dict, List, Optional, Tuple, Set
from app.modules.voice_engine.schemas import (
    CanonicalCommand,
    SemanticStatus,
    CANONICAL_DIRECTION_VECTORS,
)


class SemanticClassificationResult:
    """Structured result of semantic command classification."""
    def __init__(
        self,
        original_transcript: str,
        normalized_transcript: str,
        recognized_command: CanonicalCommand,
        recognition_confidence: float,
        classification_confidence: float,
        semantic_status: SemanticStatus,
        direction_vector: Dict[str, float],
        timestamp: float,
        language: str = "en",
        match_reason: str = "",
    ):
        self.original_transcript = original_transcript
        self.normalized_transcript = normalized_transcript
        self.recognized_command = recognized_command
        self.recognition_confidence = recognition_confidence
        self.classification_confidence = classification_confidence
        self.semantic_status = semantic_status
        self.direction_vector = direction_vector
        self.timestamp = timestamp
        self.language = language
        self.match_reason = match_reason

    def to_dict(self) -> Dict:
        return {
            "original_transcript": self.original_transcript,
            "normalized_transcript": self.normalized_transcript,
            "recognized_command": self.recognized_command.value,
            "recognition_confidence": round(self.recognition_confidence, 4),
            "classification_confidence": round(self.classification_confidence, 4),
            "semantic_status": self.semantic_status.value,
            "direction_vector": self.direction_vector,
            "timestamp": self.timestamp,
            "language": self.language,
            "match_reason": self.match_reason,
        }


class SemanticClassifier:
    """
    NLP Intent Classifier translating transcribed text into canonical motion commands.
    Enforces strict safety invariants:
    - Never guess commands from unclear or below-threshold speech.
    - STOP commands are prioritized and never rejected on loud vocal tone.
    - Extensible multi-language lexicon support (English initially, extensible to Tamil).
    """

    def __init__(
        self,
        recognition_confidence_threshold: float = 0.40,
        classification_confidence_threshold: float = 0.70,
    ):
        self.rec_threshold = recognition_confidence_threshold
        self.cls_threshold = classification_confidence_threshold

        # English Lexicon: Canonical Commands -> List of exact or regex patterns
        self._lexicon_en: Dict[CanonicalCommand, List[str]] = {
            CanonicalCommand.STOP: [
                "stop",
                "halt",
                "freeze",
                "brake",
                "hold",
                "hold position",
                "don't move",
                "dont move",
                "do not move",
                "stand still",
                "kill motion",
                "shut down",
                "emergency stop",
                "estop",
                "abort",
                "cut power",
                "stay",
                "stop operation",
                "move operation stop",
            ],
            CanonicalCommand.FORWARD: [
                "forward",
                "move forward",
                "go forward",
                "ahead",
                "straight",
                "go straight",
                "advance",
                "step forward",
                "drive forward",
                "front",
                "move front",
                "move ahead",
                "move operation forward",
            ],
            CanonicalCommand.BACKWARD: [
                "backward",
                "backwards",
                "move backward",
                "move backwards",
                "go back",
                "back up",
                "reverse",
                "step back",
                "drive back",
                "step backward",
                "back",
                "move operation backward",
                "move operation back",
            ],
            CanonicalCommand.LEFT: [
                "left",
                "move left",
                "turn left",
                "go left",
                "steer left",
                "rotate left",
                "step left",
                "slide left",
                "drive left",
                "move operation left",
            ],
            CanonicalCommand.RIGHT: [
                "right",
                "move right",
                "turn right",
                "go right",
                "steer right",
                "rotate right",
                "step right",
                "slide right",
                "drive right",
                "move operation right",
            ],
        }

        # Tamil Lexicon (Extensible for multi-lingual operator deployment)
        self._lexicon_ta: Dict[CanonicalCommand, List[str]] = {
            CanonicalCommand.STOP: [
                "நில்",
                "நிறுத்து",
                "நில்லு",
                "அப்படியே நில்",
                "இயக்கத்தை நிறுத்து",
                "nil",
                "niruthu",
                "nillu",
            ],
            CanonicalCommand.FORWARD: [
                "முன்னே போ",
                "முன்னாடி போ",
                "முன்னால் போ",
                "நேராக போ",
                "munne po",
                "munnadi",
            ],
            CanonicalCommand.BACKWARD: [
                "பின்னே போ",
                "பின்னாடி போ",
                "பின்னோக்கி போ",
                "pinne po",
                "pinnadi",
            ],
            CanonicalCommand.LEFT: [
                "இடது",
                "இடப்பக்கம்",
                "இடது பக்கம் திரும்பு",
                "idathu",
                "idappakkam",
            ],
            CanonicalCommand.RIGHT: [
                "வலது",
                "வலப்பக்கம்",
                "வலது பக்கம் திரும்பு",
                "valathu",
                "valappakkam",
            ],
        }

        # Secondary keywords for word-level matching
        self._keywords_en = {
            CanonicalCommand.STOP: {"stop", "halt", "freeze", "brake", "abort"},
            CanonicalCommand.FORWARD: {"forward", "ahead", "straight", "advance"},
            CanonicalCommand.BACKWARD: {"backward", "backwards", "reverse", "back"},
            CanonicalCommand.LEFT: {"left"},
            CanonicalCommand.RIGHT: {"right"},
        }

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalizes input transcript:
        - Lowers casing.
        - Strips punctuation except apostrophes in contractions.
        - Collapses redundant whitespace.
        """
        if not text:
            return ""
        # Lowercase
        normalized = text.lower().strip()
        # Replace common contractions
        normalized = re.sub(r"[’]", "'", normalized)
        # Strip other punctuation
        for ch in string.punctuation:
            if ch != "'":
                normalized = normalized.replace(ch, " ")
        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def classify(
        self,
        transcript: str,
        recognition_confidence: float = 1.0,
        language: str = "en",
        timestamp: Optional[float] = None,
    ) -> SemanticClassificationResult:
        """
        Classifies transcript into a CanonicalCommand with defensive ambiguity gating.
        """
        ts = timestamp or (time.time() * 1000.0)
        norm = self.normalize_text(transcript)

        # 1. Guard against empty transcript
        if not norm:
            return SemanticClassificationResult(
                original_transcript=transcript,
                normalized_transcript="",
                recognized_command=CanonicalCommand.UNKNOWN,
                recognition_confidence=0.0,
                classification_confidence=0.0,
                semantic_status=SemanticStatus.UNKNOWN,
                direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.UNKNOWN],
                timestamp=ts,
                language=language,
                match_reason="Empty audio transcript",
            )

        # 2. Guard against low speech-recognition confidence
        # Never guess from unclear speech
        if recognition_confidence < self.rec_threshold:
            return SemanticClassificationResult(
                original_transcript=transcript,
                normalized_transcript=norm,
                recognized_command=CanonicalCommand.UNCERTAIN,
                recognition_confidence=recognition_confidence,
                classification_confidence=0.0,
                semantic_status=SemanticStatus.UNCERTAIN,
                direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.UNCERTAIN],
                timestamp=ts,
                language=language,
                match_reason=f"Recognition confidence ({recognition_confidence:.2f}) below threshold ({self.rec_threshold:.2f})",
            )

        # 3. Choose lexicon dictionary based on language
        lexicon = self._lexicon_en
        if language == "ta":
            # Combine Tamil and English lexicons
            combined = {}
            for cmd in CanonicalCommand:
                combined[cmd] = self._lexicon_ta.get(cmd, []) + self._lexicon_en.get(cmd, [])
            lexicon = combined

        # 4. Critical Priority Check: Emergency STOP / "don't move"
        # In a safety critical system, STOP commands always take precedence
        for stop_phrase in lexicon.get(CanonicalCommand.STOP, []):
            if self._matches_phrase(norm, stop_phrase):
                return SemanticClassificationResult(
                    original_transcript=transcript,
                    normalized_transcript=norm,
                    recognized_command=CanonicalCommand.STOP,
                    recognition_confidence=recognition_confidence,
                    classification_confidence=1.0 if norm == stop_phrase else 0.95,
                    semantic_status=SemanticStatus.VALID,
                    direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.STOP],
                    timestamp=ts,
                    language=language,
                    match_reason=f"Matched STOP primitive phrase '{stop_phrase}'",
                )

        # Check for word-level STOP
        tokens = set(norm.split())
        if any(w in tokens for w in self._keywords_en[CanonicalCommand.STOP]):
            return SemanticClassificationResult(
                original_transcript=transcript,
                normalized_transcript=norm,
                recognized_command=CanonicalCommand.STOP,
                recognition_confidence=recognition_confidence,
                classification_confidence=0.92,
                semantic_status=SemanticStatus.VALID,
                direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.STOP],
                timestamp=ts,
                language=language,
                match_reason="Matched STOP keyword token",
            )

        # 4b. Check for generic move operation (unaccompanied by a specific direction)
        directional_tokens = {"left", "right", "back", "backward", "backwards", "reverse", "stop", "halt"}
        has_directional = any(t in tokens for t in directional_tokens)

        is_generic_move = False
        match_msg = ""
        generic_move_phrases = [
            "move operation", "start moving", "start move", "move now",
            "proceed", "advance", "run"
        ]
        if norm in {"move", "go", "drive"} or (not has_directional and len(tokens) > 0 and all(t == "move" for t in tokens)):
            is_generic_move = True
            match_msg = f"Matched move command '{norm}'"
        elif any(p in norm for p in generic_move_phrases) and not has_directional:
            is_generic_move = True
            match_msg = f"Matched generic move phrase in '{norm}'"
        elif ("move" in tokens or "go" in tokens) and not has_directional and len(tokens) <= 5:
            is_generic_move = True
            match_msg = f"Matched move action intent '{norm}'"

        if is_generic_move:
            return SemanticClassificationResult(
                original_transcript=transcript,
                normalized_transcript=norm,
                recognized_command=CanonicalCommand.FORWARD,
                recognition_confidence=recognition_confidence,
                classification_confidence=0.95,
                semantic_status=SemanticStatus.VALID,
                direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.FORWARD],
                timestamp=ts,
                language=language,
                match_reason=match_msg,
            )

        # 5. Check directional commands
        detected_commands: List[Tuple[CanonicalCommand, float, str]] = []

        for cmd in [CanonicalCommand.FORWARD, CanonicalCommand.BACKWARD, CanonicalCommand.LEFT, CanonicalCommand.RIGHT]:
            phrases = lexicon.get(cmd, [])
            for phrase in phrases:
                if norm == phrase:
                    detected_commands.append((cmd, 1.0, f"Exact match '{phrase}'"))
                    break
                elif self._matches_phrase(norm, phrase):
                    detected_commands.append((cmd, 0.94, f"Phrase match '{phrase}'"))
                    break

            # If not matched by full phrase, check single keyword match
            if not any(c[0] == cmd for c in detected_commands):
                kws = self._keywords_en.get(cmd, set())
                matched_kws = tokens.intersection(kws)
                if matched_kws:
                    # Confidence lower if transcript contains extra unrelated words
                    token_count = len(tokens)
                    conf = 0.88 if token_count <= 2 else max(0.65, 0.88 - 0.05 * (token_count - 2))
                    detected_commands.append((cmd, conf, f"Keyword match {list(matched_kws)}"))

        # 6. Ambiguity & Contradiction Resolution
        if len(detected_commands) > 1:
            # Prioritize exact/phrase match (conf >= 0.94) over loose keyword fallbacks
            max_conf = max(c[1] for c in detected_commands)
            if max_conf >= 0.94:
                detected_commands = [c for c in detected_commands if c[1] >= 0.94]

        if len(detected_commands) > 1:
            # Check if conflicting commands detected (e.g. left AND right, forward AND backward)
            unique_cmds = set(c[0] for c in detected_commands)
            if len(unique_cmds) > 1:
                # Contradictory command! Refuse to guess
                return SemanticClassificationResult(
                    original_transcript=transcript,
                    normalized_transcript=norm,
                    recognized_command=CanonicalCommand.UNCERTAIN,
                    recognition_confidence=recognition_confidence,
                    classification_confidence=0.30,
                    semantic_status=SemanticStatus.UNCERTAIN,
                    direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.UNCERTAIN],
                    timestamp=ts,
                    language=language,
                    match_reason=f"Ambiguous conflicting commands detected: {[c.value for c in unique_cmds]}",
                )

        if len(detected_commands) == 1:
            cmd, conf, reason = detected_commands[0]
            if conf >= self.cls_threshold:
                return SemanticClassificationResult(
                    original_transcript=transcript,
                    normalized_transcript=norm,
                    recognized_command=cmd,
                    recognition_confidence=recognition_confidence,
                    classification_confidence=conf,
                    semantic_status=SemanticStatus.VALID,
                    direction_vector=CANONICAL_DIRECTION_VECTORS[cmd],
                    timestamp=ts,
                    language=language,
                    match_reason=reason,
                )
            else:
                return SemanticClassificationResult(
                    original_transcript=transcript,
                    normalized_transcript=norm,
                    recognized_command=CanonicalCommand.UNCERTAIN,
                    recognition_confidence=recognition_confidence,
                    classification_confidence=conf,
                    semantic_status=SemanticStatus.UNCERTAIN,
                    direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.UNCERTAIN],
                    timestamp=ts,
                    language=language,
                    match_reason=f"Classification confidence ({conf:.2f}) below threshold ({self.cls_threshold:.2f})",
                )

        # 7. No command matched -> UNKNOWN
        return SemanticClassificationResult(
            original_transcript=transcript,
            normalized_transcript=norm,
            recognized_command=CanonicalCommand.UNKNOWN,
            recognition_confidence=recognition_confidence,
            classification_confidence=0.0,
            semantic_status=SemanticStatus.UNKNOWN,
            direction_vector=CANONICAL_DIRECTION_VECTORS[CanonicalCommand.UNKNOWN],
            timestamp=ts,
            language=language,
            match_reason="Transcript did not match any operational primitives",
        )

    @staticmethod
    def _matches_phrase(text: str, phrase: str) -> bool:
        """Checks if a whole phrase occurs with word boundaries."""
        escaped = re.escape(phrase)
        pattern = rf"(^|\s){escaped}(\s|$)"
        return bool(re.search(pattern, text))


# Global singleton instance
semantic_classifier = SemanticClassifier()

