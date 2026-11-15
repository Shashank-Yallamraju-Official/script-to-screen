"""The engine's vocabulary, declared once: what can be tuned (params) and what can be observed
(channels). The editor's controls, the checks and the command line are driven by these
declarations, so adding a parameter or a channel is one entry here, not a change in four places.

This package imports nothing else of ours; every layer may read it.
"""
from .channels import CHANNELS, Channel  # noqa: F401
from .params import PARAMS, Param  # noqa: F401
