attempts to craft sword
needs ['oak_planks', 'stick']
    pop first item
    attempt to craft  oak_planks
    needs oak_log
        attempt to craft oak_log
        fails, no recipe
        is gatherable? 
        returns source block: oak_log
        gather oak log
    craft oak planks
    success! record [gather oak log, craft oak planks]
    pop second item
    attempt to craft sticks
    success! record [craft sticks]
craft sword
success! record [gather oak log, craft planks, craft sticks, craft sword]
