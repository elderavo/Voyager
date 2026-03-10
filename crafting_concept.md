pseudo algos: 

Primitive Gathers:
Curriculum bot says: "Mine an X"  # A primitive task 
    direct execution of mineBlock(X)
    Critic identifies success (inventory of X += 1)
end

Composite and ALL crafts (even primitives):
Curriculum bot says: "Make planks" 
init task list for "make planks" skill. 
set max recursion depth
    Action bot attempts direct execution of craftItem(planks)
    if FAIL:
        Player Bot emits missing dependency: "logs"
        identify if dependency can be solved as a primitive or known skill. if not, treat as new skill to learn. 
            if PRIMITIVE/KNOWN SKILL:
                critic calls action bot to direct execute known skill
                THEN 
                append executed primitive to task list for "make planks" skill
                return to line 10 (attempt to craft original item again)
            if UNKNOWN SKILL:
                recurse to line 10, (do the same process with the unknow craft as an argument).
    
    if SUCCESS:
        critic identifies success
        save as known skill 
        (if we didn't actually know how to make the prereq's for that we will just get it some other time)

--- desired behavior example:
try to craft wood pick
init task list for craftWoodPick
fail to craft wood pick
emit missing "sticks" "planks"
    try to craft sticks
    init task list for sticks
    fail to craft sticks
    emit missing "planks"
        try to craft planks
        init task list for planks
        fail to craft planks
        emit missing "logs"
            try to gather log
            success!
            add "gather log" to task list for "craftPlanks"
        try to craft planks
        success!
        save new skill "craftPlanks"
        add "craftPlanks" to task list for "craftSticks"
    try to craft sticks
    success!
    save new skill "craftSticks"
    add "craftSticks" to task list for "craftWoodPick"
try to craft wood pick
fail
emit missing "planks"  # either turned all planks into 8x sticks or 2/4 from log into sticks, so missing 1 or 3 planks
    try to craft planks
    now a known skill, action bot execs "craftPlanks", which is composed of [mineBlock(oak_log),craftItem(planks)]
    success!
    add craftPlanks to task list for craftWoodPick
try to craft wood pick
success!
save new skill "craftWoodPick" composed of: [craftPlanks, craftSticks, craftItem(woodPick, 1)] 

craftPlanks is composed of: [mineBlock(log), craftItem(planks)]
craftSticks is composed of: [craftPlanks, craftItem(sticks)]
---

