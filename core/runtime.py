import logging
from dataclasses import dataclass

from hni.hub import Hub
from hni.network import Network
from hni.interface import Interface
from core.trace import BO42TraceEngine


logger = logging.getLogger("BO42-RUNTIME")
logging.basicConfig(level=logging.INFO)


@dataclass
class BO42RuntimeError(Exception):
    message: str
    ci: str = "GLOBAL"
    stage: str = "UNKNOWN"

    def __str__(self):
        return f"[{self.stage} | {self.ci}] {self.message} → 0"


class BO42Runtime:

    def __init__(self, trace: BO42TraceEngine = None):
        self.hub = Hub()
        self.network = Network()
        self.interface = Interface(self.network)

        self.state = "INIT"
        self.event_log = []

        # ✅ unified trace injection
        self.trace = trace or BO42TraceEngine()

        self.trace.log("RUNTIME", "INIT")

    # ================= ENTRY =================
    def run(self, ast):

        self.trace.log("RUNTIME", "START")
        logger.info("BO42 Runtime START")

        try:
            # ---------------- VERIFY ----------------
            self.state = "VERIFY"
            self.trace.log("VERIFY", "AST verification start")

            self._verify(ast)

            # ---------------- ATTR ----------------
            self.state = "ATTR"
            self.trace.log("ATTR", "Validating attributes", {
                "attr": ast.attr
            })

            self._validate_network(ast.attr)

            if not self.network.authorized:
                self.trace.log("ATTR", "Network rejected", level="WARN")
                return self._fail("NETWORK_REJECTED")

            # ---------------- EXECUTE ----------------
            self.state = "EXECUTE"
            self.trace.log("EXECUTE", "CI execution start")

            results = {}

            for ci in ast.ci_blocks:
                results[ci.name] = self._execute_ci(ci)

            self.state = "DONE"

            self.trace.log("RUNTIME", "SUCCESS", {
                "ci_count": len(results)
            })

            return results

        except BO42RuntimeError as e:
            self.trace.capture_error(e.stage, e, ci=e.ci)
            logger.error(str(e))
            self.state = "0-STATE"
            return 0

        except Exception as e:
            self.trace.capture_error("RUNTIME_FATAL", e)
            logger.error(f"UNHANDLED ERROR: {e}")
            self.state = "0-STATE"
            return 0

    # ================= VERIFY =================
    def _verify(self, ast):

        if not getattr(ast, "ce", None):
            err = BO42RuntimeError(
                message="Missing CE root",
                stage="VERIFY"
            )
            self.trace.capture_error("VERIFY", err)
            raise err

        self.trace.log("VERIFY", "AST valid")
        self.event_log.append("VERIFY_OK")

    # ================= NETWORK =================
    def _validate_network(self, attr):

        if not attr:
            self.network.authorize("invalid")
            self.trace.log("ATTR", "Empty attr → reject", level="WARN")
            return

        valid = all(v in ["valid", "verified"] for v in attr.values())

        if valid:
            self.network.authorize("valid")
            self.trace.log("ATTR", "Authorization success", attr)
        else:
            self.network.authorize("invalid")
            self.trace.log("ATTR", "Authorization failed", attr, level="WARN")

    # ================= CI EXECUTION =================
    def _execute_ci(self, ci):

        self.trace.log("CI", "START", ci=ci.name)
        logger.info(f"Executing CI: {ci.name}")

        if not self.network.authorized:
            err = BO42RuntimeError(
                message="Unauthorized CI execution",
                ci=ci.name,
                stage="EXECUTE"
            )
            self.trace.capture_error("EXECUTE", err, ci=ci.name)
            raise err

        local_memory = {}
        hub_snapshot = self.hub.snapshot()

        self.trace.log("CI", "Hub snapshot", hub_snapshot, ci=ci.name)

        for stmt in ci.body:

            payload = {
                "ci": ci.name,
                "key": stmt.key,
                "value": stmt.value,
                "hub": hub_snapshot
            }

            self.trace.log("CI_STMT", "Dispatch", payload, ci=ci.name)

            response = self.interface.send(payload)

            self.trace.log("CI_STMT", "Response", response, ci=ci.name)

            value = (
                response.get("data", {}).get("value")
                if isinstance(response, dict)
                else stmt.value
            )

            local_memory[stmt.key] = value

            self.trace.log(
                "CI_STMT",
                f"{stmt.key}={value}",
                ci=ci.name
            )

        self.event_log.append(f"CI_EXEC:{ci.name}")

        self.trace.log("CI", "END", {
            "ci": ci.name,
            "memory": local_memory
        }, ci=ci.name)

        return {
            "ci": ci.name,
            "memory": local_memory,
            "hub": hub_snapshot
        }

    # ================= FAIL =================
    def _fail(self, reason):

        self.state = "0-STATE"
        self.trace.log("RUNTIME", f"FAIL → {reason}", level="ERROR")
        logger.error(f"{reason} → 0")
        return 0