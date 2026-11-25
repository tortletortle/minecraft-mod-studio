time set midnight
weather clear
gamerule minecraft:spawn_mobs false
execute at @a run fill -3 175 -3 3 175 7 minecraft:polished_diorite
execute at @a run fill -3 176 5 3 179 6 minecraft:oxidized_copper_grate
tp @a 0.5 176 0.5 0 7
gamemode creative @a
clear @a
item replace entity @a hotbar.0 with stormshard_mod:charged_ingot
summon stormshard_mod:storm_guardian 0.5 176 3.5 {NoAI:1b,PersistenceRequired:1b,Rotation:[180f,0f]}
say MMS_MATERIAL_READY
