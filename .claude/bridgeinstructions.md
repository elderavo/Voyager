Here’s a concrete implementation checklist for the **required** changes to `VoyagerEnv` (`bridge.py`), written so you can hand it to a dev and they can execute without guessing. 
---

## 0. Ground Rule: Treat VoyagerEnv as an RPC shell, not a Gym env

Right now `VoyagerEnv`:

* Subclasses `gym.Env` but does **not** return `(obs, reward, done, truncated, info)` in `step()` or `reset()`; it just returns Mineflayer’s JSON. 
* Is only used by Voyager as a “call `/step` and get events” wrapper. 

**Instruction**

1. In `bridge.py`, change:

   ```python
   class VoyagerEnv(gym.Env):
   ```

   to:

   ```python
   class VoyagerEnv:
   ```
2. Remove unused gym imports (`gymnasium`, `ObsType`, etc.) unless something else truly depends on them (it doesn’t in this file). 
3. Keep the public methods `step`, `reset`, `close`, `render` as-is for now so Voyager doesn’t break; just stop pretending this is a Gym env.

---

## 1. Fix pause/unpause semantics

Right now both `pause()` and `unpause()` POST to the same `/pause` endpoint. That’s a hidden toggle and will desync easily. 

**Instruction**

1. **Change the Mineflayer HTTP API** to expose two clear endpoints:

   * `POST /pause` → puts server into paused state.
   * `POST /unpause` → resumes server.

2. Update `pause()`:

   * Precondition: `mineflayer.is_running and not self.server_paused`.
   * Call `POST {self.server}/pause`.
   * On 200 → set `self.server_paused = True`.
   * On non-200 → log error, leave flag unchanged.

3. Update `unpause()`:

   * Precondition: `mineflayer.is_running and self.server_paused`.
   * Call `POST {self.server}/unpause`.
   * On 200 → set `self.server_paused = False`.
   * On non-200 → log error, leave flag unchanged.

4. Remove the “toggle” semantics currently implemented:

   ````python
   def unpause(self):
       if self.mineflayer.is_running and self.server_paused:
           res = requests.post(f"{self.server}/pause")  # <-- REMOVE this
   ``` :contentReference[oaicite:5]{index=5}  

   ````

5. Add asserts/tests:

   * Calling `pause()` twice doesn’t flip back.
   * Calling `unpause()` twice doesn’t flip back.

---

## 2. Centralize response decoding (remove duplicated “double JSON” hacks)

You currently decode Mineflayer responses in three places with slightly different hacks: `check_process()`, `step()`, `reset()`. All of them:

* Decode bytes to text
* `json.loads`
* If still a `str`, `json.loads` again. 

**Instruction**

1. Create a private helper in `VoyagerEnv`:

   ```python
   def _decode_response(self, res) -> Any:
       raw_bytes = res.content
       decoded_text = raw_bytes.decode("utf-8", errors="replace")
       data = json.loads(decoded_text)
       if isinstance(data, str):
           data = json.loads(data)
       return data
   ```

2. In `step()` replace:

   ````python
   raw_bytes = res.content
   decoded_text = raw_bytes.decode('utf-8', errors='replace')
   returned_data = json.loads(decoded_text)
   ...
   if isinstance(returned_data, str):
       return json.loads(returned_data)
   return returned_data
   ``` :contentReference[oaicite:7]{index=7}  

   with:

   ```python
   returned_data = self._decode_response(res)
   ````

3. In `reset()` replace the duplicated decode/“string again” logic with `_decode_response(res)`. 

4. In `check_process()`, the block:

   ````python
   res = requests.post(...)
   ...
   raw_bytes = res.content
   decoded_text = raw_bytes.decode('utf-8', errors='replace')
   return json.loads(decoded_text)
   ``` :contentReference[oaicite:9]{index=9}  

   should also use `_decode_response`.

   ````

5. Add a unit test for `_decode_response` that:

   * Accepts proper JSON.
   * Accepts JSON-string-wrapped JSON.
   * Handles invalid Unicode gracefully.

---

## 3. Make reset semantics explicit (no hidden `reset_options["reset"] = "soft"` magic)

Current `reset()`:

* Builds `self.reset_options` with `reset: options.get("mode", "hard")`
* Immediately after the call to `check_process()` (first reset), it sets:

  ```python
  self.reset_options["reset"] = "soft"
  ```

  meaning all future resets use soft mode silently. 

This hidden mutation is exactly what leads to confusing behavior later.

**Instruction**

1. Define explicit reset “mode” constants at top of file:

   ```python
   HARD_RESET = "hard"
   SOFT_RESET = "soft"
   ```

2. In `reset()`, do **not** change `self.reset_options["reset"]` after the call. Instead:

   * Accept `options["mode"]` as either `HARD_RESET` or `SOFT_RESET`.
   * Store the **last requested mode** if you want, but don’t auto-mutate it.

3. Remove this line entirely:

   ````python
   self.reset_options["reset"] = "soft"
   ``` :contentReference[oaicite:11]{index=11}  

   ````

4. Anywhere else in the codebase that relied on “first reset hard, subsequent soft” behavior must be updated to be explicit. For example, in `Voyager.learn()` you currently use:

   * Hard reset for first run, then rely on soft resets in `env.step("")` calls. 

   That should become a deliberate call pattern (e.g., let a ResetManager decide which options to pass).

5. Add a short docstring to `reset()`:

   * Document that `options["mode"]` is required to control hard vs soft.
   * Document that the Env no longer changes mode under the hood.

---

## 4. Add a Mineflayer healthcheck and integrate it into `check_process()`

Right now `check_process()` only checks:

* If `mc_instance` is running and starts it if not.
* If `mineflayer.is_running` is false → restart process and call `/start`. 

There is **no** detection that the HTTP server is up but broken (typical JS crash behavior).

**Instruction**

1. Implement a simple healthcheck endpoint in Mineflayer:

   * `GET /health` → `{ "status": "ok" }` when ready.

2. Add a private method to `VoyagerEnv`:

   ```python
   def _healthcheck(self) -> bool:
       try:
           res = requests.get(f"{self.server}/health", timeout=2)
           return res.status_code == 200
       except requests.exceptions.RequestException:
           return False
   ```

3. Modify `check_process()`:

   * Before entering `while not self.mineflayer.is_running`, call `_healthcheck()`.
   * If `is_running` is True but `_healthcheck()` is False for N retries → treat it as crashed:

     * Call `self.mineflayer.stop()`
     * Start it again with `self.mineflayer.run()` and the existing exponential backoff.

4. Ensure that you only call `/start` once per **new** Mineflayer process:

   * e.g., after successful restart.
   * Don’t spam `/start` on every healthcheck failure.

5. Add logs clearly differentiating:

   * “Mineflayer process not running → starting”
   * “Mineflayer process running but unhealthy → restarting”

---

## 5. Make `step()` robust with an “ensure initialized” path

Right now `step()` immediately bails if `has_reset` is False: 

```python
if not self.has_reset:
    raise RuntimeError("Environment has not been reset yet")
```

And it relies on `reset()` having been called earlier. If a reset fails silently or someone forgets to call it, `step` dies.

**Instruction**

1. Add a private method:

   ```python
   def _ensure_initialized(self):
       if not self.has_reset:
           # Choose a safe default: hard reset with no inventory
           self.reset(options={"mode": HARD_RESET})
   ```

2. At the start of `step()`:

   * Replace the `if not self.has_reset: raise ...` check with:

     ```python
     self._ensure_initialized()
     ```

3. Keep the rest of `step()` logic the same:

   * `self.check_process()`
   * `self.unpause()`
   * POST `/step`
   * decode via `_decode_response`
   * `self.pause()`

4. This gives you a safety net:

   * Voyager can still explicitly manage reset behavior.
   * But you don’t hard-crash on a missing reset.

5. Add a unit/integration test:

   * Calling `step()` without prior `reset()` should now produce a proper events list, not an exception.

---

## 6. Consolidate Mineflayer (re)start flows

`get_mineflayer_process()` + `check_process()` are currently doing:

* Process spawn
* `/start` call
* Double JSON decode
* Retry loops with exponential backoff, but only around `/start`. 

Given you’re going to introduce a `MineflayerClient` later, but for now we keep it in this file:

**Instruction**

1. In `get_mineflayer_process()`, **only** construct the `SubprocessMonitor`. Do not start it yet. 

2. In `check_process()`:

   * If `self.mc_instance` exists and isn’t running → start it and set `self.mc_port` as you do now. 
   * If Mineflayer process isn’t running or `_healthcheck()` is False → start or restart it and call the `/start` endpoint once per restart.
   * Use `_decode_response` for the return payload.

3. Narrow the responsibilities:

   * `check_process()` should guarantee:

     * There is a running, healthy Mineflayer process.
     * The server has been successfully `/start`ed with `self.reset_options`.
   * It should **not** do arbitrary sleeps except those strictly necessary for process startup/backoff.

4. Prefer constant maximum retry counts:

   * For process start attempts.
   * For `/start` HTTP failures.
   * Raise `RuntimeError` with clear message when exhausted.

---

## 7. Don’t attempt to track world state in VoyagerEnv

This is more a “don’t do” than a change, but important for the rest of your architecture:

* Do **not** add inventory/position/hunger tracking into `VoyagerEnv`.
* All world semantics should live in `WorldStateTracker` (outside this file).
* `VoyagerEnv` should only ever return the raw Mineflayer “events list” from `step()` and `reset()`.

This aligns `VoyagerEnv` with the TaskSpec/Router/Executor design you’re building.

---

## 8. Quick summary for the team

If you need to write a short ticket summary:

> Refactor `VoyagerEnv` (`bridge.py`) to be a minimal, robust RPC wrapper around the Mineflayer HTTP server:
>
> * Remove `gym.Env` inheritance.
> * Fix pause/unpause to use distinct endpoints.
> * Add a centralized `_decode_response()` and replace all ad-hoc JSON decoding.
> * Make reset semantics explicit; don’t silently flip hard→soft.
> * Add a Mineflayer healthcheck and integrate it into `check_process()`.
> * Add `_ensure_initialized()` so `step()` auto-resets if needed instead of crashing.
> * Keep `VoyagerEnv` stateless w.r.t. world semantics; world state moves to a separate tracker.

