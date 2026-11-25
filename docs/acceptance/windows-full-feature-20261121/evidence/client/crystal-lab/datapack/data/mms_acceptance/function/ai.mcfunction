tellraw @a {text:'MMS_HEALTH_BEFORE_X100 ',extra:[{score:{name:'before',objective:'mms_health'}}]}
tellraw @a {text:'MMS_HEALTH_AFTER_X100 ',extra:[{score:{name:'observed',objective:'mms_health'}}]}
tellraw @a {text:'MMS_LOOT_COMMAND_SUCCESS ',extra:[{score:{name:'loot',objective:'mms_health'}}]}
execute as @a store result score crystal_count mms_health run clear @s crystal_lab:pulse_crystal 0
tellraw @a {text:'MMS_CRYSTAL_INVENTORY ',extra:[{score:{name:'crystal_count',objective:'mms_health'}}]}
item replace entity @a hotbar.0 with crystal_lab:charged_ingot
execute at @a run fill -7 159 -7 7 173 7 minecraft:stone
execute at @a store success score ore_place mms_health run place feature crystal_lab:storm_crystal_ore 0 167 0
execute at @a store result score ore_count mms_health run fill -7 159 -7 7 173 7 minecraft:stone replace crystal_lab:storm_crystal_ore
tellraw @a {text:'MMS_ORE_PLACE ',extra:[{score:{name:'ore_place',objective:'mms_health'}}]}
tellraw @a {text:'MMS_ORE_BLOCKS ',extra:[{score:{name:'ore_count',objective:'mms_health'}}]}
effect give @a minecraft:resistance 20 2 true
effect give @a minecraft:instant_health 1 2 true
execute at @a run data merge entity @e[type=crystal_lab:storm_guardian,limit=1,sort=nearest] {NoAI:0b}
schedule function mms_acceptance:quiet 8s replace
say MMS_CASE ai_live
