from dataclasses import dataclass, field
from typing import List, Dict, Optional
import logging

from boal.core.trace import BO42TraceEngine

logger = logging.getLogger("BO42-AST")
logging.basicConfig(level=logging.INFO)


# ---------------- ERROR ----------------
class BO42ASTError(Exception):
    def __init__(self, message, line=None, column=None):
        context = f"[Line {line}, Col {column}]" if line else ""
        super().__init__(f"{context} {message} → 0")


# =========================================================
# TRACE HELPER (SAFE INJECTION LAYER)
# =========================================================
def _trace(trace, stage, msg, data=None, node=None):
    if trace:
        trace.log(
            stage=stage,
            message=msg,
            data={
                "node": node.__class__.__name__ if node else None,
                "data": data
            }
        )


# ---------------- BASE NODE ----------------
@dataclass(frozen=True)
class ASTNode:
    node_type: str
    line: int = 0
    column: int = 0


# ---------------- PROGRAM ----------------
@dataclass(frozen=True)
class Program(ASTNode):
    ce: str = ""
    attr: Dict[str, str] = field(default_factory=dict)
    ci_blocks: List["CIBlock"] = field(default_factory=list)

    def validate(self, trace: Optional[BO42TraceEngine] = None):

        _trace(trace, "AST", "VALIDATE_PROGRAM_START", {
            "ce": self.ce,
            "attr": self.attr
        }, self)

        if not self.ce:
            err = BO42ASTError("Missing CE root", self.line, self.column)
            if trace:
                trace.capture_error("AST", err)
            raise err

        for ci in self.ci_blocks:
            ci.validate(trace)

        _trace(trace, "AST", "VALIDATE_PROGRAM_OK", None, self)


# ---------------- CI BLOCK ----------------
@dataclass(frozen=True)
class CIBlock(ASTNode):
    name: str = ""
    body: List["Statement"] = field(default_factory=list)

    def validate(self, trace: Optional[BO42TraceEngine] = None):

        _trace(trace, "AST", f"VALIDATE_CI:{self.name}", {
            "stmt_count": len(self.body)
        }, self)

        if not self.name:
            err = BO42ASTError("CI block missing name", self.line, self.column)
            if trace:
                trace.capture_error("AST", err, {"ci": self.name})
            raise err

        for stmt in self.body:
            stmt.validate(trace, ci=self.name)

        _trace(trace, "AST", f"VALIDATE_CI_OK:{self.name}", None, self)


# ---------------- STATEMENT ----------------
@dataclass(frozen=True)
class Statement(ASTNode):
    key: str = ""
    value: str = ""

    def validate(self, trace: Optional[BO42TraceEngine] = None, ci: str = None):

        _trace(trace, "AST", f"VALIDATE_STMT:{self.key}", {
            "value": self.value,
            "ci": ci
        }, self)

        if not self.key:
            err = BO42ASTError("Statement missing key", self.line, self.column)
            if trace:
                trace.capture_error("AST", err, {"ci": ci})
            raise err

        if self.value is None:
            err = BO42ASTError("Statement missing value", self.line, self.column)
            if trace:
                trace.capture_error("AST", err, {"ci": ci})
            raise err

        _trace(trace, "AST", f"VALIDATE_STMT_OK:{self.key}", {"ci": ci}, self)