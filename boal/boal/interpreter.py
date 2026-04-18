import os
import logging
import inspect

from boal.core.lexer import BOALLexer
from boal.core.parser import BOALParser

from boal.security.control_plane import ControlPlane
from boal.security.guard import Guard

from boal.hni.hub import Hub
from boal.hni.network import Network
from boal.hni.interface import Interface


logger = logging.getLogger("BO42-INTERPRETER")
logging.basicConfig(level=logging.INFO)


class BOALInterpreter:

    def __init__(self, trace=None):

        self.trace = trace

        # HNI LAYER
        self.hub = Hub()
        self.network = Network()
        self.interface = Interface(self.network)
        self.guard = Guard(self.network, self.hub)

        # CONTROL PLANE (safe trace injection)
        self.engine = self._safe_init(
            ControlPlane,
            network=self.network,
            hub=self.hub,
            interface=self.interface,
            guard=self.guard
        )

        logger.info("BO42 Interpreter initialized (trace-safe mode)")

    # ================= SAFE INJECTION SYSTEM =================
    def _safe_init(self, cls, **kwargs):

        """
        Only inject trace if constructor supports it
        """

        if not self.trace:
            return cls(**kwargs)

        sig = inspect.signature(cls.__init__)

        if "trace" in sig.parameters:
            kwargs["trace"] = self.trace

        return cls(**kwargs)

    # ================= FILE ENTRY =================
    def run_file(self, filepath: str):

        if self.trace:
            self.trace.log("RUN", f"Loading file {filepath}")

        if not filepath.endswith(".boal"):
            raise Exception("BO42 ERROR: Invalid file type → 0")

        if not os.path.exists(filepath):
            raise Exception("BO42 ERROR: File not found → 0")

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        return self.run(code)

    # ================= CORE PIPELINE =================
    def run(self, code: str):

        try:
            logger.info("BO42 PIPELINE START")

            if self.trace:
                self.trace.log("PIPELINE", "Start")

            # ---------------- LEXER ----------------
            lexer = self._safe_init(BOALLexer, code=code)
            tokens = lexer.tokenize()

            if self.trace:
                self.trace.log("LEXER", "Tokenization complete", len(tokens))

            # ---------------- PARSER ----------------
            parser = self._safe_init(BOALParser, tokens=tokens)
            ast = parser.parse()

            if self.trace:
                self.trace.log("PARSER", "AST build complete", {
                    "ce": getattr(ast, "ce", None),
                    "ci_count": len(getattr(ast, "ci_blocks", []))
                })

            # ---------------- EXECUTION ----------------
            result = self.engine.execute(ast)

            if self.trace:
                self.trace.log("EXECUTION", "Execution complete", result)

            logger.info("BO42 PIPELINE SUCCESS")

            return result

        except Exception as e:

            if self.trace:
                self.trace.capture_error("PIPELINE", e)

            logger.error(f"PIPELINE ERROR: {e}")
            return 0