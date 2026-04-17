import logging
import sys

from boal.interpreter import BOALInterpreter
from core.trace import BO42TraceEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BO42-RUN")


def main():

    trace = BO42TraceEngine()

    logger.info("BO42 runtime starting")

    # 🔥 START CORRELATED TRACE SESSION
    run_id = trace.new_run()

    engine = BOALInterpreter(trace=trace)

    try:
        filepath = "programs/main.boal"

        trace.log("RUN", "START", {"file": filepath, "run_id": run_id})

        result = engine.run_file(filepath)

        trace.log("RUN", "END", {"status": "SUCCESS", "run_id": run_id})

        print("BO42 OUTPUT:", result)

        # =========================
        # TRACE TIMELINE (RUN-SCOPED)
        # =========================
        print("\n--- TRACE TIMELINE ---")
        for ev in trace.timeline(run_id=run_id)[-10:]:
            print(ev)

        return 0

    except Exception as e:

        trace.capture_error("RUN", e, run_id=run_id)

        logger.error("BO42 EXECUTION FAILED")

        print("BO42 ERROR:", str(e))

        # =========================
        # LAST EVENTS (RUN SCOPED)
        # =========================
        print("\n--- TRACE (LAST 10 EVENTS) ---")
        for event in trace.tail(10):
            print(event)

        # =========================
        # ERROR TRACE (GLOBAL ROOT CAUSE)
        # =========================
        print("\n--- ERROR TRACE ---")
        print(trace.error_trace())

        # =========================
        # STAGE ISOLATION (RUN SCOPED)
        # =========================
        print("\n--- PARSER TRACE ---")
        for event in trace.filter(stage="PARSER", run_id=run_id)[-5:]:
            print(event)

        print("\n--- LEXER TRACE ---")
        for event in trace.filter(stage="LEXER", run_id=run_id)[-5:]:
            print(event)

        return 0


if __name__ == "__main__":
    sys.exit(main())