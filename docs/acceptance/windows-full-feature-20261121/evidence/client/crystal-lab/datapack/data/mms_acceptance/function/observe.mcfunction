execute as @a store result score observed mms_health run data get entity @s Health 100
execute if score observed mms_health matches 1800.. unless score done mms_health matches 1 run function mms_acceptance:pass
execute unless score done mms_health matches 1 run schedule function mms_acceptance:observe 1s replace
