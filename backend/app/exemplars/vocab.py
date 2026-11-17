"""Allowed values for calibrated exemplars. They mirror the CHECK constraints of Asad's feedback_exemplars table
(app/models/exemplar.py), so a value accepted here can never be rejected by the database."""
VERDICTS = ("TRUE_POSITIVE", "FALSE_POSITIVE")
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
TIERS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
