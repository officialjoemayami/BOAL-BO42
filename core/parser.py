import logging
from core.ast import Program, CIBlock, Statement, BO42ASTError
from core.trace import BO42TraceEngine

logger = logging.getLogger("BO42-PARSER")


class ParseState:
    PROGRAM = "PROGRAM"
    ATTR = "ATTR"
    CI = "CI"
    CI_BODY = "CI_BODY"


class BOALParser:

    def __init__(self, tokens, trace: BO42TraceEngine = None):
        self.tokens = tokens
        self.pos = 0
        self.state = ParseState.PROGRAM

        # ✅ attach trace engine
        self.trace = trace or BO42TraceEngine()

    # ---------------- CORE ----------------
    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        tok = self.current()
        self.pos += 1

        if tok:
            self.trace.log("PARSER_ADVANCE", f"{tok.type}:{tok.value}", {
                "line": tok.line,
                "col": tok.column
            })

        return tok

    def expect(self, token_type):
        tok = self.advance()

        if not tok:
            err = BO42ASTError(f"Unexpected EOF, expected {token_type}")
            self.trace.capture_error("EXPECT", err)
            raise err

        if tok.type != token_type:
            err = BO42ASTError(
                f"Expected {token_type}, got {tok.type}",
                tok.line,
                tok.column
            )
            self.trace.capture_error("EXPECT", err, {
                "expected": token_type,
                "got": tok.type
            })
            raise err

        return tok

    # ---------------- ENTRY ----------------
    def parse(self):
        logger.info("BO42 Parser v2 starting")

        ce_name = None
        attr = {}
        ci_blocks = []

        try:
            while self.current():

                tok = self.current()
                self.trace.log("PARSER_STATE", "Processing token", {
                    "type": tok.type,
                    "value": tok.value,
                    "line": tok.line,
                    "col": tok.column
                })

                # ---------------- CE ----------------
                if tok.type == "KEYWORD" and tok.value == "ce":
                    self.state = ParseState.PROGRAM
                    self.trace.log("CE", "Parsing CE block")

                    self.advance()
                    ce_name = self.expect("IDENTIFIER").value

                    self.trace.log("CE", f"CE name set → {ce_name}")

                # ---------------- ATTR ----------------
                elif tok.type == "KEYWORD" and tok.value == "attr":
                    self.state = ParseState.ATTR
                    self.trace.log("ATTR", "Parsing ATTR")

                    self.advance()

                    key = self.expect("IDENTIFIER").value
                    self.expect("EQUALS")
                    value = self.advance().value

                    attr[key] = value

                    self.trace.log("ATTR", f"{key}={value}")

                # ---------------- CI ----------------
                elif tok.type == "KEYWORD" and tok.value == "ci":
                    self.state = ParseState.CI
                    self.trace.log("CI", "Entering CI block")

                    self.advance()
                    ci = self.parse_ci()
                    ci_blocks.append(ci)

                    self.trace.log("CI", f"CI parsed → {ci.name}")

                # ---------------- EOF ----------------
                elif tok.type == "EOF":
                    self.trace.log("EOF", "End of file reached")
                    break

                # ---------------- ERROR ----------------
                else:
                    err = BO42ASTError(
                        f"Invalid syntax at token {tok.type}:{tok.value}",
                        tok.line,
                        tok.column
                    )
                    self.trace.capture_error("PARSER", err, {
                        "token": tok.type,
                        "value": tok.value
                    })
                    raise err

            if not ce_name:
                err = BO42ASTError("Missing CE block → 0")
                self.trace.capture_error("PARSER", err)
                raise err

            program = Program(
                node_type="PROGRAM",
                ce=ce_name,
                attr=attr,
                ci_blocks=ci_blocks
            )

            self.trace.log("PROGRAM", "AST successfully built", {
                "ce": ce_name,
                "attr": attr,
                "ci_count": len(ci_blocks)
            })

            return program

        except Exception as e:
            self.trace.capture_error("PARSER_FATAL", e)
            raise

    # ---------------- CI BLOCK ----------------
    def parse_ci(self):

        self.state = ParseState.CI_BODY

        name = self.expect("IDENTIFIER").value
        self.trace.log("CI", f"CI name → {name}")

        self.expect("LBRACE")

        body = []

        while self.current() and self.current().type != "RBRACE":

            tok = self.current()

            if tok.type == "IDENTIFIER":

                key = self.advance().value
                self.expect("EQUALS")
                value = self.advance().value
                self.expect("SEMICOLON")

                stmt = Statement(
                    node_type="STATEMENT",
                    key=key,
                    value=value
                )

                body.append(stmt)

                self.trace.log("CI_STATEMENT", f"{key}={value}", {
                    "ci": name
                })

            else:
                err = BO42ASTError(
                    f"Invalid CI body token: {tok.type}",
                    tok.line,
                    tok.column
                )
                self.trace.capture_error("CI_BODY", err, {
                    "ci": name,
                    "token": tok.type
                })
                raise err

        self.expect("RBRACE")

        return CIBlock(
            node_type="CI",
            name=name,
            body=body
        )