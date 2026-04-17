import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from hni.network import Network
from hni.hub import Hub
from hni.interface import Interface
from security.guard import Guard


# ---------------- LOGGING ----------------
logger = logging.getLogger("BO42-CONTROL-KERNEL")
logging.basicConfig(level=logging.INFO)


# ---------------- ERROR ----------------
@dataclass
class BO42ControlError(Exception):
    message: str
    stage: str = "CONTROL"

    def __str__(self):
        return f"[CONTROL | {self.stage}] {self.message} → 0"


# ---------------- CONTROL PLANE ----------------
class ControlPlane:

    def __init__(self, network: Network, hub: Hub, interface: Interface, guard: Guard, trace=None):

        self.network = network
        self.hub = hub
        self.interface = interface
        self.guard = guard

        self.trace = trace

        self.audit_ledger: List[Dict[str, Any]] = []

        logger.info("BO42 EXECUTION KERNEL initialized")

        if self.trace:
            self.trace.log("CONTROL", "INIT")

    # =====================================================
    # MAIN EXECUTION
    # =====================================================
    def execute(self, ast):

        logger.info("BO42 EXECUTION START")

        run_id = None
        span_id = None

        if self.trace:
            run_id = self.trace.new_run()
            span_id = self.trace._start_span("CONTROL", "EXECUTE")

            self.trace.log("CONTROL", "EXECUTION_START", run_id=run_id, span_id=span_id)

        try:
            # 1. VALIDATE AST
            self._validate_ast(ast, run_id, span_id)

            # 2. AUTHORIZE
            self._authorize(ast.attr, run_id, span_id)

            if not self.network.authorized:
                return self._fail("NETWORK_DENIED", run_id, span_id)

            # 3. HUB SNAPSHOT
            hub_snapshot = self.hub.snapshot()

            if self.trace:
                self.trace.log(
                    "CONTROL",
                    "HUB_SNAPSHOT",
                    {
                        "keys": list(hub_snapshot.keys())
                    },
                    run_id=run_id,
                    span_id=span_id
                )

            # 4. EXECUTE CI BLOCKS
            results = {}

            for ci in ast.ci_blocks:

                ci_span = None
                if self.trace:
                    ci_span = self.trace._start_span("CONTROL_CI", ci.name)

                    self.trace.log(
                        "CONTROL",
                        "CI_START",
                        {
                            "ci": ci.name,
                            "stmt_count": len(ci.body)
                        },
                        ci=ci.name,
                        run_id=run_id,
                        span_id=ci_span
                    )

                results[ci.name] = self._execute_ci(ci, hub_snapshot, run_id, ci_span)

                if self.trace:
                    self.trace.log(
                        "CONTROL",
                        "CI_END",
                        {"ci": ci.name},
                        ci=ci.name,
                        run_id=run_id,
                        span_id=ci_span
                    )

                    self.trace._end_span(ci_span)

            # 5. SUCCESS
            self.audit_ledger.append({
                "status": "SUCCESS",
                "ci_count": len(ast.ci_blocks)
            })

            if self.trace:
                self.trace.log(
                    "CONTROL",
                    "EXECUTION_SUCCESS",
                    results,
                    run_id=run_id,
                    span_id=span_id
                )

                self.trace._end_span(span_id)

            logger.info("BO42 EXECUTION SUCCESS")

            return results

        except BO42ControlError as e:

            logger.error(str(e))

            if self.trace:
                self.trace.capture_error("CONTROL", e, run_id=run_id, span_id=span_id)

            self.audit_ledger.append({
                "status": "FAILED",
                "reason": e.message
            })

            return 0

        except Exception as e:

            logger.error(f"UNHANDLED EXECUTION ERROR: {e}")

            if self.trace:
                self.trace.capture_error("CONTROL", e, run_id=run_id, span_id=span_id)

            return 0

    # =====================================================
    # AST VALIDATION
    # =====================================================
    def _validate_ast(self, ast, run_id=None, span_id=None):

        if not hasattr(ast, "ce") or not ast.ce:
            error = BO42ControlError("Missing CE root", stage="VALIDATION")

            if self.trace:
                self.trace.capture_error("CONTROL", error, run_id=run_id, span_id=span_id)

            raise error

        if self.trace:
            self.trace.log("CONTROL", "AST_VALIDATION_OK", run_id=run_id, span_id=span_id)

    # =====================================================
    # AUTHORIZATION
    # =====================================================
    def _authorize(self, attr: Dict[str, Any], run_id=None, span_id=None):

        valid = all(v in ["valid", "verified"] for v in attr.values())

        if self.trace:
            self.trace.log(
                "CONTROL",
                "AUTH_CHECK",
                {"valid": valid, "attr": attr},
                run_id=run_id,
                span_id=span_id
            )

        if valid:
            self.network.authorize("valid")

            if self.trace:
                self.trace.log("CONTROL", "AUTH_SUCCESS", run_id=run_id, span_id=span_id)
        else:
            error = BO42ControlError("Invalid attribution", stage="AUTH")

            if self.trace:
                self.trace.capture_error("CONTROL", error, run_id=run_id, span_id=span_id)

            raise error

    # =====================================================
    # CI EXECUTION
    # =====================================================
    def _execute_ci(self, ci, hub_snapshot: dict, run_id=None, span_id=None):

        logger.info(f"Executing CI: {ci.name}")

        local_memory = {}

        for stmt in ci.body:

            packet = {
                "ci": ci.name,
                "key": stmt.key,
                "value": stmt.value,
                "hub": hub_snapshot
            }

            if self.trace:
                self.trace.log(
                    "CONTROL",
                    "GUARD_CHECK",
                    {"ci": ci.name, "key": stmt.key},
                    ci=ci.name,
                    run_id=run_id,
                    span_id=span_id
                )

            self.guard.enforce(ci.name, packet)

            if self.trace:
                self.trace.log(
                    "CONTROL",
                    "GUARD_PASS",
                    {"ci": ci.name, "key": stmt.key},
                    ci=ci.name,
                    run_id=run_id,
                    span_id=span_id
                )

            response = self.interface.send(packet)

            if self.trace:
                self.trace.log(
                    "CONTROL",
                    "INTERFACE_RESPONSE",
                    {"ci": ci.name, "key": stmt.key, "response": response},
                    ci=ci.name,
                    run_id=run_id,
                    span_id=span_id
                )

            local_memory[stmt.key] = response.get("data", {}).get("value", stmt.value)

        self.audit_ledger.append({
            "ci": ci.name,
            "status": "EXECUTED"
        })

        return {
            "ci": ci.name,
            "memory": local_memory,
            "hub": hub_snapshot
        }

    # =====================================================
    # FAIL
    # =====================================================
    def _fail(self, reason: str, run_id=None, span_id=None):

        logger.error(f"EXECUTION FAILED → {reason}")

        if self.trace:
            self.trace.log("CONTROL", "FAIL", {"reason": reason}, run_id=run_id, span_id=span_id)

        return 0

    # =====================================================
    # AUDIT
    # =====================================================
    def get_audit_ledger(self):

        if self.trace:
            self.trace.log("CONTROL", "AUDIT_ACCESS")

        return tuple(self.audit_ledger)