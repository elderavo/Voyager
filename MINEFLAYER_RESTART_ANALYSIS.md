# Mineflayer Process Restart & Hang Analysis

## Why Mineflayer Restarts So Often

### 1. **Deliberate Restart on env.reset()**
**Location:** [bridge.py:174](voyager/env/bridge.py#L174)

```python
def reset(self, *, seed=None, options=None):
    # ...
    self.unpause()
    self.mineflayer.stop()  # ← DELIBERATELY STOPS MINEFLAYER
    time.sleep(1)  # wait for mineflayer to exit

    returned_data = self.check_process()  # ← RESTARTS IT HERE
```

**Why:** Every time `env.reset()` is called (which happens when starting a new task), the mineflayer process is INTENTIONALLY stopped and restarted. This is by design to ensure a clean state.

**When it happens:**
- Initial setup when Voyager starts
- Between curriculum tasks (if using hard reset mode)
- When switching between different environments

### 2. **Automatic Recovery from Crashes**
**Location:** [bridge.py:88-96](voyager/env/bridge.py#L88-L96)

```python
def check_process(self):
    retry = 0
    while not self.mineflayer.is_running:
        print("Mineflayer process has exited, restarting")
        self.mineflayer.run()
        if not self.mineflayer.is_running:
            if retry > 3:
                raise RuntimeError("Mineflayer process failed to start")
```

**Why:** If the mineflayer Node.js process crashes for ANY reason (JavaScript error, timeout, OOM, etc.), Python detects it and auto-restarts.

**Common crash causes:**
- Unhandled JavaScript exceptions in skill code
- Node.js OOM (out of memory)
- Network errors when connecting to Minecraft server
- Pathfinding errors that cause the bot to get stuck indefinitely

### 3. **Called Before EVERY env.step()**
**Location:** [bridge.py:132](voyager/env/bridge.py#L132), [voyager.py:239](voyager/voyager.py#L239)

```python
def step(self, code: str, programs: str = ""):
    if not self.has_reset:
        raise RuntimeError("Environment has not been reset yet")
    self.check_process()  # ← CHECKS AND RESTARTS IF NEEDED
```

**Result:** Even during normal execution, if mineflayer crashed between steps, it gets restarted automatically.

---

## What Causes Hangs (and Why They Take Forever)

### 1. **Pathfinding Timeouts**
**The Problem:** Mineflayer's pathfinding (via mineflayer-pathfinder plugin) can get stuck trying to find impossible paths.

**Scenarios:**
```javascript
// Bot tries to pathfind to a location that's:
// - Blocked by bedrock
// - In a completely different dimension
// - Surrounded by lava with no safe path
// - Too far away (>1000 blocks)
await bot.pathfinder.goto(goal);  // ← HANGS HERE
```

**Why it hangs:** The pathfinding algorithm keeps searching for a valid path, consuming CPU and never timing out by default.

**Current timeout:** `step_timeout=600` (10 minutes!) in [bridge.py:26](voyager/env/bridge.py#L26)

### 2. **Connection Retry Loops**
**Location:** [bridge.py:102-123](voyager/env/bridge.py#L102-L123)

```python
# Retry connection with exponential backoff
max_retries = 5
for attempt in range(max_retries):
    try:
        res = requests.post(
            f"{self.server}/start",
            json=self.reset_options,
            timeout=self.step_timeout,  # ← 600 SECONDS!
        )
```

**Why it hangs:**
- If mineflayer HTTP server is slow to respond, Python waits up to 10 minutes PER retry
- With 5 retries + exponential backoff, this can take ~50+ minutes total
- The HTTP server might be slow because the Node.js event loop is blocked (pathfinding, infinite loop in skill code, etc.)

### 3. **Infinite Loops in Generated Code**
**Example:**
```javascript
async function mineWood(bot) {
    while (true) {  // ← LLM generated this
        await mineBlock(bot, 'oak_log', 1);
        // Forgot to check inventory or add break condition
    }
}
```

**Result:** Bot mines forever until `step_timeout` (10 minutes), then Python kills the connection.

### 4. **Bot Gets Physically Stuck**
**Scenarios:**
- Bot falls in a hole and can't pathfind out
- Bot is in water and keeps trying to pathfind but drowning interrupts it
- Bot is being attacked by mobs and can't complete movement
- Bot is in a 1x1 space trying to pathfind to a block above/below

**Why it hangs:** Pathfinding keeps retrying, movement keeps getting interrupted, but the code doesn't detect "stuck" state.

### 5. **Resource Collection Never Completes**
```javascript
// Task: Collect 64 oak_logs
// Problem: There are only 20 oak_logs in the area
await collectBlocks(bot, 'oak_log', 64);  // ← SEARCHES FOREVER
```

**Result:** Bot wanders farther and farther looking for resources that don't exist.

---

## How to Detect "Stuck" vs "Busy" States

### Current System Has NO Stuck Detection
The current code cannot differentiate between:
- ✅ **Legitimate work:** Bot mining 64 blocks (takes 5-10 minutes)
- ❌ **Stuck:** Bot trying to pathfind to impossible location (wastes 10 minutes)

### Proposed Solution: Implement Progress Monitoring

#### **1. Add Progress Callbacks to Primitives**

Modify the mineflayer code to emit progress events:

```javascript
// In mineflayer/lib/primitives.js
async function mineBlock(bot, blockType, count) {
    let mined = 0;
    let lastProgress = Date.now();

    while (mined < count) {
        const block = bot.findBlock({
            matching: mcData.blocksByName[blockType].id,
            maxDistance: 32
        });

        if (!block) {
            // NO PROGRESS: Can't find block
            bot.emit('primitive_progress', {
                primitive: 'mineBlock',
                status: 'searching',
                progress: mined / count,
                lastUpdate: lastProgress
            });

            // If searching for >30 seconds, give up
            if (Date.now() - lastProgress > 30000) {
                throw new Error(`Cannot find ${blockType} nearby`);
            }

            await bot.wait(1000);
            continue;
        }

        await bot.dig(block);
        mined++;
        lastProgress = Date.now();

        // PROGRESS MADE
        bot.emit('primitive_progress', {
            primitive: 'mineBlock',
            status: 'working',
            progress: mined / count,
            lastUpdate: lastProgress
        });
    }
}
```

#### **2. Monitor Progress from Python Side**

Add progress tracking to [bridge.py](voyager/env/bridge.py):

```python
class VoyagerEnv(gym.Env):
    def __init__(self, ...):
        # ...
        self.last_progress_time = None
        self.progress_timeout = 30  # No progress for 30s = stuck
        self.max_step_duration = 300  # Max 5 minutes per step

    def step(self, code: str, programs: str = ""):
        self.check_process()
        self.unpause()

        self.last_progress_time = time.time()

        # Start step execution in background thread
        result_queue = queue.Queue()
        thread = threading.Thread(
            target=self._execute_step_with_monitoring,
            args=(code, programs, result_queue)
        )
        thread.start()

        # Monitor for progress
        while thread.is_alive():
            elapsed = time.time() - self.last_progress_time

            if elapsed > self.progress_timeout:
                # NO PROGRESS FOR 30+ SECONDS - BOT IS STUCK
                print(f"⚠️ Bot appears stuck (no progress for {elapsed}s)")
                self._interrupt_execution("Bot stuck: no progress detected")
                break

            if time.time() - start_time > self.max_step_duration:
                # STEP TAKING TOO LONG
                print(f"⚠️ Step timeout ({self.max_step_duration}s)")
                self._interrupt_execution("Step timeout exceeded")
                break

            time.sleep(1)

        thread.join(timeout=5)
        return result_queue.get()

    def _interrupt_execution(self, reason):
        """Force stop current execution and provide feedback."""
        # Send interrupt signal to mineflayer
        requests.post(f"{self.server}/interrupt", json={"reason": reason})

        # Return error event that critic agent can process
        return [{
            "type": "interrupted",
            "reason": reason,
            "suggestion": self._get_stuck_suggestion(reason)
        }]

    def _get_stuck_suggestion(self, reason):
        """Provide helpful suggestions based on stuck reason."""
        if "pathfind" in reason.lower():
            return "Bot couldn't reach destination. Try checking if path is blocked or destination is too far."
        elif "no progress" in reason.lower():
            return "Bot hasn't made progress. Resource might not exist nearby or bot is physically stuck."
        else:
            return "Execution interrupted. Try simplifying the task or checking for infinite loops."
```

#### **3. Add Progress Events to Mineflayer HTTP API**

In `voyager/env/mineflayer/index.js`, add progress endpoint:

```javascript
// Track current primitive execution
let currentPrimitive = null;
let lastProgressUpdate = Date.now();

bot.on('primitive_progress', (data) => {
    currentPrimitive = data;
    lastProgressUpdate = Date.now();
});

// Add progress endpoint
app.get('/progress', (req, res) => {
    res.json({
        primitive: currentPrimitive,
        idleTime: Date.now() - lastProgressUpdate,
        position: bot.entity.position,
        health: bot.health,
        food: bot.food
    });
});

// Add interrupt endpoint
app.post('/interrupt', (req, res) => {
    const {reason} = req.body;
    console.log(`❌ Interrupted: ${reason}`);

    // Stop all current actions
    bot.pathfinder.stop();
    bot.stopDigging();
    bot.clearControlStates();

    // Return error to Python
    res.json({
        success: false,
        error: reason,
        interrupted: true
    });
});
```

#### **4. Update Critic Agent to Handle Stuck States**

Modify critic prompts to recognize and suggest fixes for stuck situations:

```python
# In critic_agent.py
def check_task_success(self, events, task, context, ...):
    # Check if bot was interrupted for being stuck
    interrupted_events = [e for e in events if e[0] == 'interrupted']

    if interrupted_events:
        reason = interrupted_events[-1][1]['reason']
        suggestion = interrupted_events[-1][1]['suggestion']

        critique = f"""Task failed: {reason}

{suggestion}

Suggested fixes:
1. Check if the resource exists nearby before attempting to collect it
2. Add inventory checks to avoid collecting more than available
3. Use shorter pathfinding distances (maxDistance: 32 instead of 100+)
4. Add timeout conditions to loops (e.g., max 10 attempts)
5. Check bot position/health before continuing
"""
        return False, critique
```

---

## Implementation Priority

### **High Priority (Immediate):**
1. ✅ **Reduce `step_timeout`** from 600s to 120s (2 minutes max per primitive)
2. ✅ **Add `/interrupt` endpoint** to mineflayer HTTP server
3. ✅ **Add progress monitoring** to Python `env.step()`

### **Medium Priority (This Week):**
4. **Add `primitive_progress` events** to top 5 primitives (mineBlock, craftItem, smeltItem, placeItem, killMob)
5. **Update critic prompts** to suggest fixes for stuck scenarios

### **Low Priority (Future):**
6. Implement predictive stuck detection (e.g., bot in same position for 10s while pathfinding)
7. Add automatic recovery strategies (e.g., jump, move random direction, teleport to spawn)
8. Collect metrics on stuck patterns to improve primitive implementations

---

## Example: Before vs After

### **Before (Current System):**
```
Task: Collect 64 oak_logs
Bot: *searches for oak_log*
Bot: *can't find any nearby*
Bot: *walks farther away searching*
Bot: *still searching...*
[9 minutes pass]
Bot: *still searching...*
[10 minutes - timeout]
Python: "Step timeout, restarting mineflayer"
[1 minute restart]
LLM: *generates same code again*
[Repeat 3 more times, wasting 40+ minutes]
```

### **After (With Progress Monitoring):**
```
Task: Collect 64 oak_logs
Bot: *searches for oak_log*
Bot: *can't find any nearby*
[30 seconds pass with no progress]
Python: "⚠️ Bot stuck: no progress for 30s"
Python: "Interrupting execution"
Bot: *stops searching*
Critic: "Task failed: Bot couldn't find oak_log nearby.
         Suggestion: Check inventory or explore further before collecting."
LLM: *generates improved code with existence check*
async function collectOakLogs(bot) {
    const nearbyLog = bot.findBlock({matching: 'oak_log', maxDistance: 32});
    if (!nearbyLog) {
        bot.chat("No oak_log nearby, exploring first");
        await exploreUntil(bot, () => bot.findBlock({matching: 'oak_log', maxDistance: 32}));
    }
    await mineBlock(bot, 'oak_log', 64);
}
```

**Time saved:** 39 minutes ✅
**Bot learns:** Check before collecting ✅
**User frustration:** Significantly reduced ✅

---

## Quick Fix You Can Implement Right Now

Edit [bridge.py:26](voyager/env/bridge.py#L26):

```python
# Change this:
step_timeout=600,  # 10 MINUTES

# To this:
step_timeout=120,  # 2 MINUTES
```

This alone will reduce hang duration from 10 minutes to 2 minutes, making the system 5x more responsive when bot gets stuck.
