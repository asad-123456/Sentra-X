"""Application security log: failed logins, access denials and admin actions. Never log passwords or tokens."""
import logging

security_log = logging.getLogger("sentrax.security")
if not security_log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    security_log.addHandler(_handler)
    security_log.setLevel(logging.INFO)
    # propagate stays True so tests (caplog) and any root handler also see these records
