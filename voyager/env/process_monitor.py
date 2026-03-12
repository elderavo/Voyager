import time
import re
import warnings
from typing import List

import psutil
import subprocess
import logging
import threading

import voyager.utils as U
from voyager.utils import get_logger


class SubprocessMonitor:
    def __init__(
        self,
        commands: List[str],
        name: str,
        ready_match: str = r".*",
        log_path: str = "logs",
        callback_match: str = r"^(?!x)x$",  # regex that will never match
        callback: callable = None,
        finished_callback: callable = None,
        cwd: str = None,
    ):
        self.commands = commands
        start_time = time.strftime("%Y%m%d_%H%M%S")
        self.name = name

        # File logger — writes subprocess stdout to its own timestamped log file
        self.logger = logging.getLogger(name)
        handler = logging.FileHandler(U.f_join(log_path, f"{start_time}.log"), encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Voyager hierarchy logger — propagates to run.log / console
        self._vlogger = get_logger(f"voyager.env.subprocess.{name}")

        self.process = None
        self.ready_match = ready_match
        self.ready_event = None
        self.ready_line = None
        self.callback_match = callback_match
        self.callback = callback
        self.finished_callback = finished_callback
        self.thread = None
        self.cwd = cwd

    def _start(self):
        self.logger.info(f"Starting subprocess with commands: {self.commands}")
        if self.cwd:
            self.logger.info(f"Working directory: {self.cwd}")

        self.process = psutil.Popen(
            self.commands,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',  # Replace invalid characters instead of crashing
            cwd=self.cwd,
        )
        self._vlogger.info(f"Subprocess '{self.name}' started with PID {self.process.pid}")
        for line in iter(self.process.stdout.readline, ""):
            self.logger.info(line.strip())
            if re.search(self.ready_match, line):
                self.ready_line = line
                self.logger.info("Subprocess is ready.")
                self._vlogger.info(f"Subprocess '{self.name}' is ready")
                self.ready_event.set()
            if re.search(self.callback_match, line):
                self.callback()
        if not self.ready_event.is_set():
            self.ready_event.set()
            warnings.warn(f"Subprocess {self.name} failed to start.")
            self._vlogger.warning(f"Subprocess '{self.name}' exited before becoming ready")
        if self.finished_callback:
            self.finished_callback()

    def run(self):
        self.ready_event = threading.Event()
        self.ready_line = None
        self.thread = threading.Thread(target=self._start)
        self.thread.start()
        self.ready_event.wait()

    def stop(self):
        self.logger.info("Stopping subprocess.")
        if self.process and self.process.is_running():
            self.process.terminate()
            self.process.wait()

    @property
    def is_running(self):
        if self.process is None:
            return False
        return self.process.is_running()
