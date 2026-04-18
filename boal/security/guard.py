import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from boal.core.trace import BO42TraceEngine


# ---------------- LOGGING ----------------
logger = logging.getLogger("BO42-GUARD")
logging.basicConfig(level=logging.INFO)


# ---------------- GUARD ERROR ----------------
@dataclass
class BO42GuardError(Exception):
    message: str
    ci: str = None
    rule: str = None

    def __str__(self):
        return f"[GUARD | {self.rule} | {self.ci}] {self.message} → 0"


# ---------------- GUARD ----------------
class Guard:

    def __init__(self, network, hub, trace: Optional[BO42TraceEngine] = None):
        self.network = network
        self.hub = hub
        self.trace = trace

        self.violation_log = []

        logger.info("BO42 GUARD initialized (runtime firewall active)")

        if self.trace:
            self.trace.log("GUARD", "INIT")

    # =====================================================
    # MAIN ENFORCEMENT PIPELINE
    # =====================================================
    def enforce(self, ci_name: str, payload: Dict[str, Any]):

        if self.trace:
            self.trace.log("GUARD", "ENTER", {
                "ci": ci_name,
                "keys": list(payload.keys()) if isinstance(payload, dict) else None
            })

        logger.info(f"Guard check → CI: {ci_name}")

        # -------------------------------------------------
        # RULE 1: NETWORK AUTH
        # -------------------------------------------------
        if not self.network.authorized:
            self._violation(ci_name, "UNAUTHORIZED_EXECUTION")

            if self.trace:
                self.trace.log("GUARD", "BLOCK_NETWORK_UNAUTHORIZED", {
                    "ci": ci_name
                })

            raise BO42GuardError(
                message="Execution blocked (no attribution)",
                ci=ci_name,
                rule="NETWORK_GATE"
            )

        # -------------------------------------------------
        # RULE 2: PAYLOAD VALIDATION
        # -------------------------------------------------
        if not isinstance(payload, dict):
            self._violation(ci_name, "INVALID_PAYLOAD")

            if self.trace:
                self.trace.capture_error(
                    "GUARD",
                    Exception("Invalid payload type"),
                    context={"ci": ci_name, "payload": str(payload)},
                    ci=ci_name
                )

            raise BO42GuardError(
                message="Invalid CI payload type",
                ci=ci_name,
                rule="PAYLOAD_VALIDATION"
            )

        # -------------------------------------------------
        # RULE 3: HUB INTEGRITY
        # -------------------------------------------------
        if "hub" in payload and not isinstance(payload["hub"], dict):
            self._violation(ci_name, "HUB_TAMPER_ATTEMPT")

            if self.trace:
                self.trace.log("GUARD", "BLOCK_HUB_TAMPER", {
                    "ci": ci_name
                })

            raise BO42GuardError(
                message="Invalid HUB access attempt",
                ci=ci_name,
                rule="HUB_INTEGRITY"
            )

        # -------------------------------------------------
        # RULE 4: CI NAME VALIDATION
        # -------------------------------------------------
        if not ci_name or not isinstance(ci_name, str):
            self._violation(ci_name, "INVALID_CI_NAME")

            if self.trace:
                self.trace.log("GUARD", "BLOCK_INVALID_CI", {
                    "ci": ci_name
                })

            raise BO42GuardError(
                message="Invalid CI identifier",
                ci=ci_name,
                rule="CI_VALIDATION"
            )

        # -------------------------------------------------
        # PASS
        # -------------------------------------------------
        self._pass(ci_name)

        return True

    # =====================================================
    # PASS EVENT
    # =====================================================
    def _pass(self, ci_name: str):

        self.violation_log.append({
            "ci": ci_name,
            "status": "PASS"
        })

        logger.info(f"Guard PASS → {ci_name}")

        if self.trace:
            self.trace.log("GUARD", "PASS", {
                "ci": ci_name
            })

    # =====================================================
    # VIOLATION TRACKING
    # =====================================================
    def _violation(self, ci_name, reason):

        self.violation_log.append({
            "ci": ci_name,
            "reason": reason
        })

        logger.warning(f"GUARD VIOLATION → {ci_name} | {reason}")

        if self.trace:
            self.trace.log("GUARD", "VIOLATION", {
                "ci": ci_name,
                "reason": reason
            })

    # =====================================================
    # AUDIT
    # =====================================================
    def get_violations(self):
        return tuple(self.violation_log)