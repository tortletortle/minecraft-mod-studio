say MMS_CASE prepare
time set noon
weather clear
difficulty normal
gamerule minecraft:natural_health_regeneration false
gamerule minecraft:spawn_mobs false
scoreboard objectives add mms_health dummy
scoreboard players reset done mms_health
execute at @a run kill @e[type=!minecraft:player,distance=..25]
execute at @a run fill -4 175 -4 4 175 8 minecraft:smooth_stone
tp @a 0.5 176 0.5 0 19
setblock 0 176 5 crystal_lab:pulse_block
summon crystal_lab:storm_guardian 2.0 176 5.2 {NoAI:1b,PersistenceRequired:1b,Rotation:[180f,0f]}
clear @a
item replace entity @a hotbar.0 with crystal_lab:pulse_crystal
item replace entity @a hotbar.1 with minecraft:diamond_pickaxe
execute as @a store success score loot mms_health run loot spawn 0.5 176 2.5 mine 0 176 5 minecraft:diamond_pickaxe
scoreboard players get loot mms_health
gamemode survival @a
damage @a[limit=1] 10 minecraft:generic
schedule function mms_acceptance:before 2s replace
