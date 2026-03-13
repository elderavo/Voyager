"""
Voyager logging infrastructure.

Usage
-----
In run_voyager.py (once, before constructing Voyager):
    from voyager.utils.logger import setup_logging
    setup_logging()

In every module:
    from voyager.utils import get_logger
    logger = get_logger(__name__)

Log files written to ./logs/<YYYYMMDD_HHMMSS>/
    run.log     – everything (DEBUG+)
    errors.log  – warnings and above only
    llm.log     – LLM requests/responses (records tagged extra={'llm': True})
"""

import logging
import os
import re
import time

# ---------------------------------------------------------------------------
# ANSI stripping
# ---------------------------------------------------------------------------

_ANSI_ESCAPE = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_FILE_FMT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"

_LEVEL_BADGE = {
    "DEBUG":    "\033[90m[D]\033[0m",
    "INFO":     "\033[37m[I]\033[0m",
    "WARNING":  "\033[33m[W]\033[0m",
    "ERROR":    "\033[31m[E]\033[0m",
    "CRITICAL": "\033[41m[!]\033[0m",
}


class _StripAnsiFormatter(logging.Formatter):
    """File formatter: strips ANSI colour codes so log files stay clean."""

    def format(self, record: logging.LogRecord) -> str:
        # Work on a shallow copy so we don't mutate the original record
        record = logging.makeLogRecord(record.__dict__)
        record.msg = _strip_ansi(str(record.msg))
        if record.args:
            # Pre-render args so strip_ansi can work on the full message
            try:
                record.msg = record.msg % record.args
            except Exception:
                pass
            record.args = None
        return super().format(record)


class _ColorConsoleFormatter(logging.Formatter):
    """Console formatter: compact HH:MM:SS + level badge, preserves caller's ANSI."""

    def format(self, record: logging.LogRecord) -> str:
        badge = _LEVEL_BADGE.get(record.levelname, "")
        ts = time.strftime("%H:%M:%S")
        return f"{ts} {badge} {record.getMessage()}"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class _LLMFilter(logging.Filter):
    """Only passes records tagged with extra={'llm': True}."""

    def filter(self, record: logging.LogRecord) -> bool:
        return bool(getattr(record, "llm", False))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(
    log_path: str = "./logs",
    console_level: int = logging.INFO,
) -> str:
    """
    Configure the 'voyager' root logger with four handlers.

    Must be called once before constructing Voyager().

    Parameters
    ----------
    log_path : str
        Directory under which a timestamped session folder is created.
    console_level : int
        Minimum level printed to the terminal (default INFO).

    Returns
    -------
    str
        The session ID string (e.g. '20260312_143000') so the caller can
        display the log directory path to the user.
    """
    session_id = time.strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(log_path, session_id)
    os.makedirs(session_dir, exist_ok=True)

    root = logging.getLogger("voyager")

    # Guard against duplicate handlers if setup_logging() is called more than once
    if root.handlers:
        return session_id

    root.setLevel(logging.DEBUG)  # handlers filter individually

    file_fmt = _StripAnsiFormatter(fmt=_FILE_FMT, datefmt=_FILE_DATEFMT)

    # run.log — everything
    fh_run = logging.FileHandler(
        os.path.join(session_dir, "run.log"), encoding="utf-8"
    )
    fh_run.setLevel(logging.DEBUG)
    fh_run.setFormatter(file_fmt)

    # errors.log — WARNING and above
    fh_err = logging.FileHandler(
        os.path.join(session_dir, "errors.log"), encoding="utf-8"
    )
    fh_err.setLevel(logging.WARNING)
    fh_err.setFormatter(file_fmt)

    # llm.log — records tagged extra={'llm': True}
    fh_llm = logging.FileHandler(
        os.path.join(session_dir, "llm.log"), encoding="utf-8"
    )
    fh_llm.setLevel(logging.DEBUG)
    fh_llm.addFilter(_LLMFilter())
    fh_llm.setFormatter(file_fmt)

    # stdout — coloured, INFO+ by default
    sh = logging.StreamHandler()
    sh.setLevel(console_level)
    sh.setFormatter(_ColorConsoleFormatter())

    root.addHandler(fh_run)
    root.addHandler(fh_err)
    root.addHandler(fh_llm)
    root.addHandler(sh)

    return session_id


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger of the 'voyager' hierarchy.

    Call at module level:
        logger = get_logger(__name__)

    When __name__ is 'voyager.htn.orchestrator', every log line will carry
    that name, giving automatic file attribution with zero extra code.
    """
    return logging.getLogger(name)
