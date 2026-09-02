"""Combines every probe's ProbeResult for a task into one KEEP/FIX/DROP verdict,
then rolls all task verdicts up into one environment-level Trust Score. This is
the only module allowed to hold scoring-policy opinions (thresholds, weights).
"""
