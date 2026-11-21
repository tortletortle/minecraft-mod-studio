import json
from pathlib import Path

base = Path(__file__).resolve().parents[2]
pack = base / 'outputs/full-feature-acceptance-20261121/client/game/saves/MMSAcceptance/datapacks/mms_acceptance'
functions = pack / 'data/mms_acceptance/function'
tags = pack / 'data/minecraft/tags/function'
functions.mkdir(parents=True, exist_ok=True)
tags.mkdir(parents=True, exist_ok=True)
(pack / 'pack.mcmeta').write_text(json.dumps({'pack': {'description': 'MMS disposable verification fixture', 'min_format': [107, 1], 'max_format': [107, 1]}}), encoding='utf-8')
(tags / 'load.json').write_text(json.dumps({'values': ['mms_acceptance:load']}), encoding='utf-8')
scripts = {
    'load': 'schedule function mms_acceptance:prepare 3s replace',
    'prepare': '''say MMS_CASE prepare
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
 schedule function mms_acceptance:before 2s replace''',
    'before': '''execute as @a store result score before mms_health run data get entity @s Health 100
 scoreboard players get before mms_health
 say MMS_CASE press_R
 schedule function mms_acceptance:observe 1s replace''',
    'observe': '''execute as @a store result score observed mms_health run data get entity @s Health 100
 execute if score observed mms_health matches 1800.. unless score done mms_health matches 1 run function mms_acceptance:pass
 execute unless score done mms_health matches 1 run schedule function mms_acceptance:observe 1s replace''',
    'pass': '''scoreboard players set done mms_health 1
 scoreboard players get observed mms_health
 say MMS_CASE healing_observed''',
}
for name, script in scripts.items():
    (functions / f'{name}.mcfunction').write_text('\n'.join(line.strip() for line in script.splitlines()) + '\n', encoding='utf-8')
