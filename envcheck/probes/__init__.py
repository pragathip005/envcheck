"""Independent inspectors. Each probe takes a Task and returns a ProbeResult -
its own local verdict plus the evidence behind it. Probes never see each other's
output; combining verdicts across probes is scoring/'s job, not the probes'.
"""
