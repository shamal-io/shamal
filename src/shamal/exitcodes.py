"""Process exit codes. This contract is part of the public CLI interface (spec: cli-core).

0: run completed and thresholds passed
1: run completed and thresholds failed
2: execution error (engine crash, target unreachable, unexpected failure)
3: configuration error (missing/invalid config, unsupported input)
"""

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    THRESHOLDS_FAILED = 1
    EXECUTION_ERROR = 2
    CONFIG_ERROR = 3
