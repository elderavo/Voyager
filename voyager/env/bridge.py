import enum
import os.path
import time
import warnings
from typing import Any, Tuple, Dict

import requests
import json

import voyager.utils as U

from .minecraft_launcher import MinecraftInstance
from .process_monitor import SubprocessMonitor

# Reset mode constants (kept for backward compatibility)
HARD_RESET = "hard"
SOFT_RESET = "soft"


class ResetMode(str, enum.Enum):
    HARD = "hard"
    SOFT = "soft"


class VoyagerEnv:
    """
    VoyagerEnv: Minimal RPC wrapper around the Mineflayer HTTP server.

    This is NOT a Gym environment - it's a stateless bridge that:
    - Manages the Mineflayer subprocess
    - Provides step/reset/pause/unpause methods
    - Returns raw Mineflayer event data

    World state tracking should be done separately (e.g., WorldStateTracker).
    """

    def __init__(
        self,
        mc_host="localhost",
        mc_port=None,
        azure_login=None,
        server_host="http://127.0.0.1",
        server_port=None,
        step_timeout=600,
        log_path="./logs",
    ):
        if server_port is None:
            from voyager.config import config
            server_port = config.MINEFLAYER_PORT

        if not mc_port and not azure_login:
            raise ValueError("Either mc_port or azure_login must be specified")
        if mc_port and azure_login:
            warnings.warn(
                "Both mc_port and mc_login are specified, mc_port will be ignored"
            )
        self.mc_port = mc_port
        self.mc_host = mc_host
        self.azure_login = azure_login
        self.server = f"{server_host}:{server_port}"
        self.server_port = server_port
        self.step_timeout = step_timeout
        self.log_path = log_path
        self.mineflayer = self.get_mineflayer_process(server_port)
        if azure_login:
            self.mc_instance = self.get_mc_instance()
        else:
            self.mc_instance = None
        self.has_reset = False
        self.reset_options = None
        self.connected = False
        self.server_paused = False

    def get_mineflayer_process(self, server_port):
        """
        Construct the SubprocessMonitor for Mineflayer.
        Does NOT start the process - that happens in check_process().
        """
        U.f_mkdir(self.log_path, "mineflayer")
        file_path = os.path.abspath(os.path.dirname(__file__))
        mineflayer_dir = U.f_join(file_path, "mineflayer")
        return SubprocessMonitor(
            commands=[
                "node",
                "index.js",
                str(server_port),
            ],
            name="mineflayer",
            ready_match=r"Server started on port (\d+)",
            log_path=U.f_join(self.log_path, "mineflayer"),
            cwd=mineflayer_dir,
        )

    def get_mc_instance(self):
        print("Creating Minecraft server")
        U.f_mkdir(self.log_path, "minecraft")
        return MinecraftInstance(
            **self.azure_login,
            mineflayer=self.mineflayer,
            log_path=U.f_join(self.log_path, "minecraft"),
        )

    def _decode_response(self, res) -> Any:
        """
        Centralized response decoder for Mineflayer HTTP responses.

        Handles:
        - UTF-8 decoding with error replacement
        - Double JSON encoding (Mineflayer sometimes returns JSON-wrapped JSON)

        Args:
            res: requests.Response object

        Returns:
            Decoded Python data structure
        """
        raw_bytes = res.content
        decoded_text = raw_bytes.decode("utf-8", errors="replace")
        data = json.loads(decoded_text)
        # Handle double-encoded JSON
        if isinstance(data, str):
            data = json.loads(data)
        return data

    def _healthcheck(self) -> bool:
        """
        Check if Mineflayer HTTP server is healthy.

        Returns:
            True if server responds to /health endpoint, False otherwise
        """
        try:
            res = requests.get(f"{self.server}/health", timeout=2)
            return res.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def check_process(self):
        """
        Ensure Minecraft and Mineflayer processes are running and healthy.

        Responsibilities:
        - Start MC instance if needed
        - Start/restart Mineflayer if not running or unhealthy
        - Call /start endpoint once per new Mineflayer process
        - Return the initial state from /start

        Returns:
            Initial state data from Mineflayer /start endpoint
        """
        # Check and start Minecraft instance if needed
        if self.mc_instance and not self.mc_instance.is_running:
            print("Starting Minecraft server")
            self.mc_instance.run()
            self.mc_port = self.mc_instance.port
            self.reset_options["port"] = self.mc_instance.port
            print(f"Server started on port {self.reset_options['port']}")

        retry_count = 0
        max_process_retries = 3

        # Check if Mineflayer process needs to be started/restarted
        while not self.mineflayer.is_running or not self._healthcheck():
            if self.mineflayer.is_running and not self._healthcheck():
                print("Mineflayer process running but unhealthy → restarting")
                self.mineflayer.stop()
                time.sleep(0.5)
            else:
                print("Mineflayer process not running → starting")

            self.mineflayer.run()

            if not self.mineflayer.is_running:
                retry_count += 1
                if retry_count > max_process_retries:
                    raise RuntimeError(
                        f"Mineflayer process failed to start after {max_process_retries} attempts"
                    )
                else:
                    time.sleep(0.5)
                    continue

            print(self.mineflayer.ready_line)

            # Give the server a moment to fully initialize
            time.sleep(1)

            # Call /start endpoint with exponential backoff
            max_start_retries = 5
            for attempt in range(max_start_retries):
                try:
                    res = requests.post(
                        f"{self.server}/start",
                        json=self.reset_options,
                        timeout=self.step_timeout,
                    )
                    if res.status_code != 200:
                        self.mineflayer.stop()
                        raise RuntimeError(
                            f"Mineflayer /start endpoint replied with code {res.status_code}"
                        )

                    # Use centralized decoder
                    return self._decode_response(res)

                except (requests.exceptions.ConnectionError, ConnectionResetError):
                    if attempt < max_start_retries - 1:
                        wait_time = 0.5 * (2 ** attempt)  # Exponential backoff
                        print(
                            f"Connection failed (attempt {attempt + 1}/{max_start_retries}), "
                            f"retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        print(f"Failed to connect to Mineflayer after {max_start_retries} attempts")
                        raise RuntimeError(
                            f"Failed to connect to Mineflayer server after {max_start_retries} attempts"
                        )

    def _ensure_initialized(self):
        """
        Ensure the environment has been initialized (reset at least once).

        If not initialized, performs a hard reset with no inventory.
        This provides a safety net so step() doesn't crash on missing reset.
        """
        if not self.has_reset:
            print("[VoyagerEnv] Auto-initializing with hard reset (no prior reset detected)")
            self.reset(options={"mode": HARD_RESET})

    def step(
        self,
        code: str,
        programs: str = "",
    ) -> Any:
        """
        Execute a code step in Mineflayer.

        Args:
            code: JavaScript code to execute
            programs: Additional program definitions

        Returns:
            List of Mineflayer events from this step
        """
        # Ensure initialized (auto-reset if needed)
        self._ensure_initialized()

        self.check_process()
        self.unpause()

        data = {
            "code": code,
            "programs": programs,
        }
        res = requests.post(
            f"{self.server}/step", json=data, timeout=self.step_timeout
        )
        if res.status_code != 200:
            raise RuntimeError(f"Failed to step Minecraft server (status {res.status_code})")

        # Use centralized decoder
        returned_data = self._decode_response(res)

        self.pause()

        return returned_data

    def render(self):
        raise NotImplementedError("render is not implemented")

    def reset(
        self,
        *,
        seed=None,
        options=None,
    ) -> Any:
        """
        Reset the Mineflayer environment.

        Args:
            seed: Not used (kept for compatibility)
            options: Dict with reset options:
                - mode: "hard" or "soft" (REQUIRED, no longer defaults silently)
                - inventory: Dict of items (only valid for hard reset)
                - equipment: List of equipment
                - spread: Whether to spread spawn
                - wait_ticks: Ticks to wait
                - position: Spawn position

        Returns:
            Initial state events from Mineflayer

        Note:
            The environment NO LONGER silently changes mode from hard to soft.
            Callers must explicitly specify mode for each reset.
        """
        if options is None:
            options = {}

        reset_mode = options.get("mode", ResetMode.HARD)
        if isinstance(reset_mode, str):
            reset_mode = ResetMode(reset_mode)

        if options.get("inventory", {}) and reset_mode != ResetMode.HARD:
            raise RuntimeError("inventory can only be set when mode is 'hard'")

        self.reset_options = {
            "host": self.mc_host,
            "port": self.mc_port,
            "reset": reset_mode.value,  # Explicit mode - no hidden mutation
            "inventory": options.get("inventory", {}),
            "equipment": options.get("equipment", []),
            "spread": options.get("spread", False),
            "waitTicks": options.get("wait_ticks", 5),
            "position": options.get("position", None),
        }

        self.unpause()
        self.mineflayer.stop()
        time.sleep(1)  # wait for mineflayer to exit

        returned_data = self.check_process()
        self.has_reset = True
        self.connected = True

        # IMPORTANT: We do NOT mutate reset_options["reset"] here anymore!
        # Callers must explicitly control reset mode for each call.

        self.pause()

        return returned_data

    def close(self):
        """Close all connections and stop all processes."""
        self.unpause()
        if self.connected:
            res = requests.post(f"{self.server}/stop")
            if res.status_code == 200:
                self.connected = False
        if self.mc_instance:
            self.mc_instance.stop()
        self.mineflayer.stop()
        return not self.connected

    def pause(self):
        """
        Pause the Mineflayer server.

        Precondition: Mineflayer is running and not already paused
        Calls: POST /pause endpoint

        Returns:
            True if server is paused after this call
        """
        if self.mineflayer.is_running and not self.server_paused:
            try:
                res = requests.post(f"{self.server}/pause", timeout=5)
                if res.status_code == 200:
                    self.server_paused = True
                else:
                    print(f"[VoyagerEnv] Pause failed with status {res.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"[VoyagerEnv] Pause request failed: {e}")
        return self.server_paused

    def unpause(self):
        """
        Unpause the Mineflayer server.

        Precondition: Mineflayer is running and currently paused
        Calls: POST /unpause endpoint

        Returns:
            False if server is unpaused after this call, True if still paused
        """
        if self.mineflayer.is_running and self.server_paused:
            try:
                res = requests.post(f"{self.server}/unpause", timeout=5)
                if res.status_code == 200:
                    self.server_paused = False
                else:
                    print(f"[VoyagerEnv] Unpause failed with status {res.status_code}")
                    if res.headers.get('content-type') == 'application/json':
                        try:
                            print(res.json())
                        except:
                            pass
            except requests.exceptions.RequestException as e:
                print(f"[VoyagerEnv] Unpause request failed: {e}")
        return self.server_paused
