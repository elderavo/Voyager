# ✅ **PATCH 1 — executor_craft(): EXIT AFTER SUCCESS + STOP RETURNING program_code**

```diff
--- a/voyager/executor/executor.py
+++ b/voyager/executor/executor.py
@@ def executor_craft(self, item_name: str):
-        # === SUCCESS CASE (OLD) ===
-        if success:
-            print(f"✓ Craft succeeded for {item_name}")
-
-            # synthesize and register skill
-            skill_code = self.synthesize_skill(skill_name, steps)
-            self.skill_manager.register_skill(skill_name, skill_code)
-
-            return {
-                "task": f"Craft {item_name}",
-                "success": True,
-                "executor_mode": True,
-                "program_name": skill_name,
-                "program_code": skill_code,
-            }
+        # === SUCCESS CASE (NEW — TERMINATE LOOP, DO NOT RETURN program_code) ===
+        if success:
+            print(f"✓ Craft succeeded for {item_name}")
+
+            if not self.skill_manager.has_skill(skill_name):
+                skill_code = self.synthesize_skill(skill_name, steps)
+                self.skill_manager.register_skill(skill_name, skill_code)
+
+            # Hard-exit the executor. No more crafting, no re-execution.
+            return {
+                "task": f"Craft {item_name}",
+                "success": True,
+                "executor_mode": True,
+            }
```

---

# ✅ **PATCH 2 — Skill Manager: Make registration idempotent**

```diff
--- a/voyager/executor/skill_manager.py
+++ b/voyager/executor/skill_manager.py
@@ class SkillManager:
     def register_skill(self, name: str, code: str):
-        self.programs[name] = code
-        print(f"✓ Registered skill: {name}")
+        # prevent duplicate registration spam
+        if name in self.programs:
+            return
+        self.programs[name] = code
+        print(f"✓ Registered skill: {name}")
+
+    def has_skill(self, name: str) -> bool:
+        return name in self.programs
```

---

# ✅ **PATCH 3 — Dependency resolution: DO NOT re-synthesize known skills**

```diff
--- a/voyager/executor/executor.py
+++ b/voyager/executor/executor.py
@@ def resolve_dependency(self, dep):
-        # Always synthesize a skill for dependency (OLD)
-        print(f"Recursively discovering skill for: {dep}")
-        dep_skill_code = self.synthesize_and_register(dep)
-        return self.execute_skill(dep_skill_code)
+        # NEW: If skill exists → run it directly. No synthesis.
+        skill_name = f"craft{dep.title().replace('_','')}"
+
+        if self.skill_manager.has_skill(skill_name):
+            print(f"Executing known skill for dependency: {skill_name}")
+            return self.execute_skill(skill_name)
+
+        # otherwise: learn a new skill recursively (first time only)
+        print(f"Learning new skill for dependency: {dep}")
+        dep_skill_code = self.synthesize_skill(skill_name, steps=[])
+        self.skill_manager.register_skill(skill_name, dep_skill_code)
+        return self.execute_skill(skill_name)
```

---

# ✅ **PATCH 4 — Prevent infinite re-execution of synthesized skills**

The executor main retry loop currently looks like:

```
while True:
    try craft
    if fail → resolve dependencies
    continue
```

We change it so that **only ONE retry** may happen after resolving deps.
After that retry, if success → exit; if fail → exit with failure.

```diff
--- a/voyager/executor/executor.py
+++ b/voyager/executor/executor.py
@@ def executor_craft(self, item_name):
-        # OLD infinite retry loop
-        while True:
-            success, events = self.attempt_craft(item_name)
-            if not success:
-                deps = self.parse_missing_deps(events)
-                for d in deps:
-                    self.resolve_dependency(d)
-                continue
-            else:
-                # handled above
-                pass
+        # NEW: Try once → if fail, resolve deps → retry ONCE → exit
+
+        # 1st attempt
+        success, events = self.attempt_craft(item_name)
+
+        if success:
+            return self._finalize_success(item_name, steps)
+
+        # if fail: resolve deps
+        deps = self.parse_missing_deps(events)
+        for d in deps:
+            self.resolve_dependency(d)
+
+        # retry ONCE
+        success, events = self.attempt_craft(item_name)
+
+        if success:
+            return self._finalize_success(item_name, steps)
+
+        # if still failing → give up
+        return {"task": f"Craft {item_name}", "success": False, "executor_mode": True}
```

Add helper:

```diff
+    def _finalize_success(self, item_name, steps):
+        skill_name = f"craft{item_name.title().replace('_','')}"
+        if not self.skill_manager.has_skill(skill_name):
+            skill_code = self.synthesize_skill(skill_name, steps)
+            self.skill_manager.register_skill(skill_name, skill_code)
+        return {
+            "task": f"Craft {item_name}",
+            "success": True,
+            "executor_mode": True
+        }
```

---

# **RESULT**

Once these 4 patches are applied:

### ✔ No more repeated crafting after success

### ✔ No more duplicate skill registration

### ✔ Executor always stops when recipe chain completes

### ✔ Skills are not synthesized again if already known

### ✔ Executor behavior now matches your intended HTN pseudo-algorithm exactly

---


