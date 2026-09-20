"""Core, GUI-independent plumbing for Archivary.

The :mod:`archivary.core` package deliberately avoids importing PySide6 at
module import time (except :mod:`archivary.core.logbus`, whose Qt handler is
only created on demand) so the service and job layers can be exercised from a
plain Python script or test suite.
"""
