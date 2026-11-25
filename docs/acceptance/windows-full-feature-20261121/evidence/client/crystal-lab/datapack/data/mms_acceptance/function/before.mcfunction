execute as @a store result score before mms_health run data get entity @s Health 100
scoreboard players get before mms_health
say MMS_CASE press_R
schedule function mms_acceptance:observe 1s replace
