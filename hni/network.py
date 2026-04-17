import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


logger = logging.getLogger("BO42-NETWORK")
logging.basicConfig(level=logging.INFO)


# ================= ERROR =================
@dataclass
class BO42NetworkError(Exception):
    message: str
    status: Optional[str] = None

    def __str__(self):
        return f"[NETWORK | {self.status}] {self.message} → 0"


# ================= NETWORK =================
class Network:

    def __init__(self, trace=None):

        self.trace = trace

        self.__authorized: bool = False
        self.__status: Optional[str] = None
        self.session_id: Optional[str] = None

        self.__audit_log = []

        logger.info("BO42 NETWORK initialized")

        self._trace("NETWORK_INIT", "Initialized")

    # =========================================================
    # TRACE HELPERS
    # =========================================================
    def _trace(self, stage: str, message: str, data=None, level="INFO"):
        if self.trace:
            self.trace.log(stage, message, data=data, level=level)

    def _trace_error(self, stage: str, error: Exception, context=None):
        if self.trace:
            self.trace.capture_error(stage, error, context=context)

    # ================= AUTHORIZE =================
    def authorize(self, status: str, session_id: str = None):

        self._trace("NETWORK_AUTH", "ATTEMPT", {
            "status": status,
            "session_id": session_id
        })

        try:
            if status not in ["valid", "verified"]:

                self.__authorized = False
                self.__status = "REJECTED"

                event = {
                    "action": "AUTH",
                    "status": status,
                    "result": "FAIL",
                    "timestamp": datetime.utcnow().isoformat()
                }

                self.__audit_log.append(event)

                error = BO42NetworkError(
                    message="Invalid attribution",
                    status=status
                )

                self._trace_error("NETWORK_AUTH_FAIL", error, event)
                raise error

            # ================= SUCCESS =================
            self.__authorized = True
            self.__status = status
            self.session_id = session_id

            event = {
                "action": "AUTH",
                "status": status,
                "result": "SUCCESS",
                "session": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }

            self.__audit_log.append(event)

            logger.info("NETWORK AUTHORIZED")

            self._trace("NETWORK_AUTH", "SUCCESS", event)

        except Exception as e:
            self._trace_error("NETWORK_FATAL", e, {
                "status": status,
                "session_id": session_id
            })
            raise

    # ================= RESET =================
    def reset(self):

        self.__authorized = False
        self.__status = None
        self.session_id = None

        self._trace("NETWORK_RESET", "RESET")

    # ================= STATE =================
    @property
    def authorized(self) -> bool:
        return self.__authorized

    @property
    def status(self) -> Optional[str]:
        return self.__status

    # ================= SESSION =================
    def get_session(self) -> Dict[str, Any]:

        session = {
            "authorized": self.__authorized,
            "status": self.__status,
            "session_id": self.session_id
        }

        self._trace("NETWORK_SESSION", "ACCESS", session)

        return session

    # ================= AUDIT =================
    def get_audit_log(self):

        self._trace("NETWORK_AUDIT", "ACCESS", {
            "entries": len(self.__audit_log)
        })

        return tuple(self.__audit_log)