import logging
from dataclasses import dataclass
from typing import List, Optional

# ================= LOGGING =================
logger = logging.getLogger("BO42.LEXER")
logger.setLevel(logging.DEBUG)


# ================= ERROR =================
class BO42LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"[Line {line}, Col {column}] {message} → 0")
        self.line = line
        self.column = column


# ================= TOKEN =================
@dataclass(frozen=True)
class Token:
    type: str
    value: str
    line: int
    column: int


# ================= LEXER =================
class BOALLexer:

    KEYWORDS = {"ce", "ci", "attr", "verify"}
    VALUES = {"valid", "verified"}

    SINGLE_SYMBOLS = {
        "{": "LBRACE",
        "}": "RBRACE",
        "=": "EQUALS",
        ";": "SEMICOLON"
    }

    MULTI_SYMBOLS = {
        "->": "ARROW",
        "==": "EQEQ",
        ":=": "ASSIGN"
    }

    # =====================================================
    # INIT (TRACE SAFE INJECTION)
    # =====================================================
    def __init__(self, code: str, trace=None):
        self.code = code
        self.tokens: List[Token] = []

        self.line = 1
        self.i = 0
        self.column = 1

        # ✅ SAFE TRACE INJECTION (ZERO COUPLING CRASH)
        self.trace = trace

    # =====================================================
    # TRACE WRAPPERS (CRITICAL FIX)
    # =====================================================
    def _tlog(self, stage, message, data=None):
        if self.trace and hasattr(self.trace, "log"):
            try:
                self.trace.log(stage, message, data=data)
            except Exception:
                logger.debug(f"TRACE_LOG_FAILED [{stage}] {message}")

    def _tcapture(self, stage, error, context=None):
        if self.trace and hasattr(self.trace, "capture_error"):
            try:
                self.trace.capture_error(stage, error, context=context)
            except Exception:
                logger.debug(f"TRACE_CAPTURE_FAILED [{stage}] {error}")

    # =====================================================
    # MAIN ENTRY
    # =====================================================
    def tokenize(self) -> List[Token]:

        logger.info("BO42 Lexer v2 starting")

        self._tlog("LEXER", "START", {
            "line": self.line,
            "column": self.column
        })

        try:
            while self.i < len(self.code):
                char = self.code[self.i]

                if char == "\n":
                    self._tlog("LEXER", "NEWLINE")
                    self._advance_line()
                    continue

                if char.isspace():
                    self._advance()
                    continue

                if char == "/" and self._peek() == "/":
                    self._tlog("LEXER", "COMMENT_SKIP")
                    self._skip_comment()
                    continue

                if char == '"':
                    self._read_string()
                    continue

                two = self._peek(2)
                if two in self.MULTI_SYMBOLS:
                    self._tlog("LEXER", "MULTI_SYMBOL", {"value": two})
                    self._emit(self.MULTI_SYMBOLS[two], two, self.column)
                    self._advance_n(2)
                    continue

                if char in self.SINGLE_SYMBOLS:
                    self._tlog("LEXER", "SYMBOL", {"value": char})
                    self._emit(self.SINGLE_SYMBOLS[char], char, self.column)
                    self._advance()
                    continue

                if char.isalpha() or char in "_$":
                    self._read_identifier()
                    continue

                err = BO42LexerError(
                    f"Invalid character '{char}'",
                    self.line,
                    self.column
                )

                self._tcapture("LEXER", err, {
                    "char": char,
                    "line": self.line,
                    "column": self.column
                })

                raise err

            self._tlog("LEXER", "EOF")

            self.tokens.append(Token("EOF", "", self.line, self.column))

            logger.info("BO42 Lexer v2 completed successfully")
            return self.tokens

        except BO42LexerError:
            logger.exception("Lexical failure")
            raise

    # =====================================================
    # STRING
    # =====================================================
    def _read_string(self):
        start_col = self.column
        value = ""

        self._tlog("LEXER", "STRING_START")

        self._advance()

        while self.i < len(self.code):
            char = self.code[self.i]

            if char == "\n":
                err = BO42LexerError("Unterminated string", self.line, self.column)
                self._tcapture("LEXER", err)
                raise err

            if char == '"':
                self._advance()
                self._tlog("LEXER", "STRING_END", {"value": value})
                self._emit("STRING", value, start_col)
                return

            value += char
            self._advance()

        err = BO42LexerError("Unterminated string at EOF", self.line, self.column)
        self._tcapture("LEXER", err)
        raise err

    # =====================================================
    # IDENTIFIER
    # =====================================================
    def _read_identifier(self):
        start = self.i
        start_col = self.column

        while self.i < len(self.code):
            char = self.code[self.i]
            if char.isalnum() or char in "_$":
                self._advance()
            else:
                break

        word = self.code[start:self.i]

        if word in self.KEYWORDS:
            t = "KEYWORD"
        elif word in self.VALUES:
            t = "VALUE"
        else:
            t = "IDENTIFIER"

        self._tlog("LEXER", "IDENTIFIER", {
            "type": t,
            "value": word
        })

        self.tokens.append(Token(t, word, self.line, start_col))

    # =====================================================
    # HELPERS
    # =====================================================
    def _skip_comment(self):
        while self.i < len(self.code) and self.code[self.i] != "\n":
            self._advance()

    def _emit(self, ttype: str, value: str, col: Optional[int] = None):
        self._tlog("LEXER", "EMIT", {
            "type": ttype,
            "value": value
        })

        self.tokens.append(Token(ttype, value, self.line, col or self.column))

    def _advance(self, step: int = 1):
        self.i += step
        self.column += step

    def _advance_n(self, n: int):
        for _ in range(n):
            self._advance()

    def _advance_line(self):
        self.i += 1
        self.line += 1
        self.column = 1

    def _peek(self, length: int = 1) -> str:
        if self.i + length <= len(self.code):
            return self.code[self.i:self.i + length]
        return ""