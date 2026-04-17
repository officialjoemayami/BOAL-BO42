import logging
import time
import uuid
import functools
from dataclasses import dataclass, field
from typing import Any, List, Optional, Dict


logger = logging.getLogger("BO42-TRACE")


# =========================================================
# EVENT (GRAPH NODE)
# =========================================================
@dataclass
class TraceEvent:
    id: int
    ts: float
    run_id: str
    stage: str
    message: str
    data: Any = None
    ci: Optional[str] = None
    level: str = "INFO"

    # 🔥 v3 additions (correlation graph)
    span_id: Optional[str] = None
    parent_id: Optional[int] = None
    duration_ms: Optional[float] = None


# =========================================================
# TRACE ENGINE v3 (CORRELATION SYSTEM)
# =========================================================
class BO42TraceEngine:

    def __init__(self):
        self.events: List[TraceEvent] = []
        self.error: Optional[str] = None
        self._counter: int = 0

        self.current_run_id: Optional[str] = None

        # 🔥 span tracking (execution blocks)
        self.active_spans: Dict[str, Dict[str, Any]] = {}

    # =========================================================
    # RUN CONTROL
    # =========================================================
    def new_run(self) -> str:
        self.current_run_id = str(uuid.uuid4())[:8]

        self.log("TRACE", "NEW_RUN", {
            "run_id": self.current_run_id
        })

        return self.current_run_id

    # =========================================================
    # INTERNAL SPAN SYSTEM
    # =========================================================
    def _start_span(self, stage, ci):
        span_id = str(uuid.uuid4())[:8]

        self.active_spans[span_id] = {
            "start": time.time(),
            "stage": stage,
            "ci": ci,
            "last_event_id": None
        }

        return span_id

    def _end_span(self, span_id):
        span = self.active_spans.get(span_id)
        if not span:
            return None

        duration = (time.time() - span["start"]) * 1000
        span["duration_ms"] = round(duration, 3)

        return span

    # =========================================================
    # CORE LOG
    # =========================================================
    def log(self, stage, message, data=None, ci=None,
            level="INFO", run_id=None,
            span_id=None, parent_id=None):

        self._counter += 1

        event = TraceEvent(
            id=self._counter,
            ts=time.time(),
            run_id=run_id or self.current_run_id or "GLOBAL",
            stage=stage,
            message=message,
            data=data,
            ci=ci,
            level=level,
            span_id=span_id,
            parent_id=parent_id
        )

        self.events.append(event)

        # link span → last event
        if span_id and span_id in self.active_spans:
            self.active_spans[span_id]["last_event_id"] = event.id

        if level == "ERROR":
            logger.error(f"[{stage}] {message}")
        elif level == "WARN":
            logger.warning(f"[{stage}] {message}")
        else:
            logger.debug(f"[{stage}] {message}")

        return event.id

    # =========================================================
    # ERROR CAPTURE (CORRELATED)
    # =========================================================
    def capture_error(self, stage, error, context=None, ci=None,
                      run_id=None, span_id=None):

        self.error = str(error)

        return self.log(
            stage=stage,
            message="ERROR",
            data={
                "error": str(error),
                "context": context
            },
            ci=ci,
            level="ERROR",
            run_id=run_id,
            span_id=span_id
        )

    # =========================================================
    # 🚀 AUTO TRACE DECORATOR (v3 CORRELATED)
    # =========================================================
    def trace(self, stage: str = None, ci: str = None, capture_args: bool = False):

        def decorator(func):

            @functools.wraps(func)
            def wrapper(*args, **kwargs):

                _stage = stage or func.__module__.split(".")[-1].upper()
                _ci = ci

                if _ci is None and args and hasattr(args[0], "__class__"):
                    _ci = args[0].__class__.__name__

                span_id = self._start_span(_stage, _ci)

                start = time.time()

                try:
                    self.log(
                        _stage,
                        f"ENTER {func.__name__}",
                        data={"args": str(args), "kwargs": str(kwargs)} if capture_args else None,
                        ci=_ci,
                        span_id=span_id
                    )

                    result = func(*args, **kwargs)

                    self.log(
                        _stage,
                        f"EXIT {func.__name__}",
                        data={
                            "duration_ms": round((time.time() - start) * 1000, 3),
                            "result": str(result)[:200]
                        },
                        ci=_ci,
                        span_id=span_id
                    )

                    self._end_span(span_id)

                    return result

                except Exception as e:

                    self.capture_error(
                        _stage,
                        e,
                        context={
                            "function": func.__name__
                        },
                        ci=_ci,
                        span_id=span_id
                    )

                    self._end_span(span_id)
                    raise

            return wrapper

        return decorator

    # =========================================================
    # FILTERING
    # =========================================================
    def filter(self, stage=None, ci=None, run_id=None, level=None):

        result = self.events

        if stage:
            result = [e for e in result if e.stage == stage]

        if ci:
            result = [e for e in result if e.ci == ci]

        if run_id:
            result = [e for e in result if e.run_id == run_id]

        if level:
            result = [e for e in result if e.level == level]

        return [e.__dict__ for e in result]

    # =========================================================
    # TIMELINE
    # =========================================================
    def timeline(self, run_id=None):

        events = self.events

        if run_id:
            events = [e for e in events if e.run_id == run_id]

        return [
            {
                "id": e.id,
                "time": round(e.ts, 6),
                "run_id": e.run_id,
                "stage": e.stage,
                "ci": e.ci,
                "message": e.message,
                "level": e.level,
                "span_id": e.span_id,
                "parent_id": e.parent_id,
                "duration_ms": e.duration_ms
            }
            for e in events
        ]

    # =========================================================
    # ERROR TRACE
    # =========================================================
    def error_trace(self):

        if not self.error:
            return None

        return {
            "error": self.error,
            "context": self.filter(level="ERROR")[-5:]
        }

    # =========================================================
    # GRAPH VIEW (🔥 NEW)
    # =========================================================
    def graph(self):
        """Returns execution graph structure"""

        return {
            "nodes": [e.__dict__ for e in self.events],
            "spans": self.active_spans
        }

    # =========================================================
    # UTILITIES
    # =========================================================
    def tail(self, n=10):
        return [e.__dict__ for e in self.events[-n:]]

    def dump(self):
        return [e.__dict__ for e in self.events]


# =========================================================
# GLOBAL SINGLETON
# =========================================================
TRACE = BO42TraceEngine()