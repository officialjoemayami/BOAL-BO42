import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional


# ---------------- LOGGING ----------------
logger = logging.getLogger("BO42-INTERFACE")
logging.basicConfig(level=logging.INFO)


# ---------------- ERROR ----------------
@dataclass
class BO42InterfaceError(Exception):
    message: str
    ci: Optional[str] = None
    stage: Optional[str] = None

    def __str__(self):
        return f"[INTERFACE | {self.stage} | {self.ci}] {self.message} → 0"


# ---------------- INTERFACE ----------------
class Interface:

    def __init__(self, network, trace=None):

        self.network = network
        self.trace = trace
        self.execution_log = []

        logger.info("BO42 INTERFACE initialized (CI execution layer active)")

        self._trace("INTERFACE_INIT", "Initialized")

    # =========================================================
    # TRACE HELPERS (STANDARDIZED)
    # =========================================================
    def _trace(self, stage: str, message: str, data=None, ci=None, level="INFO"):
        if self.trace:
            self.trace.log(stage, message, data=data, ci=ci, level=level)

    def _trace_error(self, stage: str, error: Exception, context=None, ci=None):
        if self.trace:
            self.trace.capture_error(stage, error, context=context, ci=ci)

    # ================= CI EXECUTION =================
    def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:

        ci_name = payload.get("ci")

        self._trace("INTERFACE_SEND", "START", {
            "ci": ci_name,
            "payload_keys": list(payload.keys())
        }, ci=ci_name)

        try:
            # 🔐 STEP 1: NETWORK GATE
            if not self.network.authorized:

                error = BO42InterfaceError(
                    message="CI execution blocked (no attribution)",
                    ci=ci_name,
                    stage="NETWORK_GATE"
                )

                self._trace_error("INTERFACE_GATE", error, payload, ci=ci_name)
                raise error

            key = payload.get("key")
            value = payload.get("value")
            hub = payload.get("hub")

            # 🔐 STEP 2: VALIDATION
            if ci_name is None or key is None:

                error = BO42InterfaceError(
                    message="Invalid CI payload structure",
                    ci=ci_name,
                    stage="VALIDATION"
                )

                self._trace_error("INTERFACE_VALIDATION", error, payload, ci=ci_name)
                raise error

            # 🧠 STEP 3: EXECUTION
            result_value = self._execute_logic(value, hub)

            response = {
                "ci": ci_name,
                "data": {
                    "key": key,
                    "value": result_value
                }
            }

            # 📊 STEP 4: AUDIT
            self.execution_log.append({
                "ci": ci_name,
                "key": key,
                "status": "SUCCESS"
            })

            logger.info(f"CI EXECUTED → {ci_name}::{key}")

            self._trace("INTERFACE_SEND", "SUCCESS", {
                "ci": ci_name,
                "key": key,
                "input": value,
                "output": result_value
            }, ci=ci_name)

            return response

        except Exception as e:

            self._trace_error("INTERFACE_FATAL", e, payload, ci=ci_name)
            raise

    # ================= CORE EXECUTION =================
    def _execute_logic(self, value: Any, hub: Dict[str, Any]) -> Any:

        self._trace("INTERFACE_LOGIC", "EXECUTE", {
            "value": value
        })

        if isinstance(value, str) and value.startswith("$hub:"):
            hub_key = value.replace("$hub:", "")
            resolved = hub.get(hub_key)

            self._trace("INTERFACE_LOGIC", "HUB_RESOLVE", {
                "key": hub_key,
                "resolved": resolved
            })

            return resolved

        return value

    # ================= AUDIT =================
    def get_execution_log(self):

        self._trace("INTERFACE_AUDIT", "ACCESS", {
            "entries": len(self.execution_log)
        })

        return tuple(self.execution_log)