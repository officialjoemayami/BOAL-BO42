import sys
import argparse
import logging

from boal.boal.interpreter import BOALInterpreter
from boal.core.trace import BO42TraceEngine


logger = logging.getLogger("BO42-CLI")
logging.basicConfig(level=logging.INFO)


def run_command(filepath: str, enable_trace: bool):
    trace = BO42TraceEngine() if enable_trace else None

    engine = BOALInterpreter(trace=trace)

    try:
        result = engine.run_file(filepath)

        print("\nBO42 OUTPUT:")
        print(result)

        if enable_trace and trace:
            print("\n--- TRACE (LAST 20 EVENTS) ---")
            for ev in trace.tail(20):
                print(ev)

        return 0

    except Exception as e:
        print(f"\nBO42 ERROR: {e}")

        if enable_trace and trace:
            print("\n--- ERROR TRACE ---")
            print(trace.error_trace())

            print("\n--- TRACE (LAST 20 EVENTS) ---")
            for ev in trace.tail(20):
                print(ev)

        return 1


def main():
    parser = argparse.ArgumentParser(prog="boal", description="BOAL Runtime CLI")

    subparsers = parser.add_subparsers(dest="command")

    # 👉 boal run <file> [--trace]
    run_parser = subparsers.add_parser("run", help="Run a BOAL program")
    run_parser.add_argument("file", help="Path to .boal file")
    run_parser.add_argument("--trace", action="store_true", help="Enable trace output")

    args = parser.parse_args()

    if args.command == "run":
        return run_command(args.file, args.trace)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())