"""State machine — tracks pipeline state transitions."""
import time
import logging
from galaxy.types import SessionState

log = logging.getLogger("galaxy.orchestrator")

# Valid state transitions
TRANSITIONS = {
    SessionState.RECEIVED: [SessionState.VALIDATING, SessionState.FAILED],
    SessionState.VALIDATING: [SessionState.PLANNING, SessionState.FAILED],
    SessionState.PLANNING: [SessionState.CACHE_CHECK, SessionState.DISCOVERING, SessionState.FAILED],
    SessionState.CACHE_CHECK: [SessionState.DISCOVERING, SessionState.COMPLETED],
    SessionState.DISCOVERING: [SessionState.COLLECTING, SessionState.FAILED],
    SessionState.COLLECTING: [SessionState.WEB_EXTRACTING, SessionState.PROCESSING, SessionState.FAILED],
    SessionState.WEB_EXTRACTING: [SessionState.PROCESSING, SessionState.FAILED],
    SessionState.PROCESSING: [SessionState.BUILDING, SessionState.FAILED],
    SessionState.BUILDING: [SessionState.COMPLETED, SessionState.FAILED],
    SessionState.COMPLETED: [],
    SessionState.FAILED: [],
    SessionState.CANCELLED: [],
}


class StateMachine:
    """Tracks and validates pipeline state transitions."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = SessionState.RECEIVED
        self.history: list[dict] = []
        self._record(SessionState.RECEIVED)
    
    def transition(self, new_state: SessionState) -> bool:
        """Transition to a new state. Returns True if valid."""
        valid_next = TRANSITIONS.get(self.state, [])
        if new_state not in valid_next:
            log.error(f"Invalid transition: {self.state.value} → {new_state.value}")
            return False
        
        old = self.state
        self.state = new_state
        self._record(new_state)
        log.info(f"State: {old.value} → {new_state.value}")
        return True
    
    def _record(self, state: SessionState):
        self.history.append({"state": state.value, "timestamp": time.time()})
    
    def can_transition(self, new_state: SessionState) -> bool:
        return new_state in TRANSITIONS.get(self.state, [])
    
    def get_history(self) -> list[dict]:
        return self.history
