import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional


# ---------------- LOGGING ----------------
logger = logging.getLogger("BO42-HUB")
logging.basicConfig(level=logging.INFO)


# ---------------- ERROR ----------------
@dataclass
class BO42HubError(Exception):
    message: str
    key: str = None

    def __str__(self):
        return f"[HUB | {self.key}] {self.message} → 0"


# ---------------- HUB ----------------
class Hub:

    def __init__(self, trace=None):

        self.trace = trace

        self.__data: Dict[str, Any] = {
            "truth": "BO42"
        }

        self.__audit_log = []

        logger.info("BO42 HUB initialized (read-only CE layer)")

        self._trace("HUB_INIT", "Initialized", {
            "keys": list(self.__data.keys())
        })

    # =========================================================
    # TRACE WRAPPER (CLEAN STANDARDIZATION)
    # =========================================================
    def _trace(self, stage: str, message: str, data=None, level="INFO"):
        if self.trace:
            self.trace.log(stage, message, data=data, level=level)

    def _trace_error(self, stage: str, error: Exception, context=None):
        if self.trace:
            self.trace.capture_error(stage, error, context=context)

    # ================= READ =================
    def read(self, key: str) -> Any:

        if not isinstance(key, str):
            error = BO42HubError("Invalid key type", key=str(key))
            self._trace_error("HUB_READ", error, {"key": key})
            raise error

        value = self.__data.get(key)
        status = "SUCCESS" if value is not None else "MISS"

        self.__audit_log.append({
            "action": "READ",
            "key": key,
            "status": status
        })

        logger.info(f"HUB READ → {key}")

        self._trace("HUB_READ", "READ operation", {
            "key": key,
            "status": status,
            "value": value if status == "SUCCESS" else None
        })

        return value

    # ================= WRITE (BLOCKED) =================
    def write(self, key: str, value: Any):

        logger.critical(f"HUB WRITE ATTEMPT BLOCKED → {key}")

        error = BO42HubError(
            message="HUB is immutable (CE core protection)",
            key=key
        )

        self._trace_error("HUB_WRITE", error, {
            "key": key,
            "attempted_value": value
        })

        raise error

    # ================= SNAPSHOT =================
    def snapshot(self) -> Dict[str, Any]:

        snapshot = dict(self.__data)

        self._trace("HUB_SNAPSHOT", "Snapshot created", {
            "size": len(snapshot)
        })

        return snapshot

    # ================= AUDIT =================
    def get_audit_log(self):

        self._trace("HUB_AUDIT", "Audit log accessed", {
            "entries": len(self.__audit_log)
        })

        return tuple(self.__audit_log)