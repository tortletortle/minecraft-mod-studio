package studio.acceptance;

import net.fabricmc.fabric.api.gametest.v1.GameTest;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.entity.EntityTypes;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.Vec3;
import studio.generated.m_73746f726d73686172645f6d6f64.*;

public final class WorldGameTests {
    private static Identifier id(String path) {
        return Identifier.fromNamespaceAndPath("stormshard_mod",path);
    }
    private static void pass(String id, GameTestHelper h) {
        System.out.println("MMS_WORLD_PASS " + id);
        h.succeed();
    }
    private static void floor(GameTestHelper h) {
        for(int x=0;x<8;x++) for(int z=0;z<8;z++) h.setBlock(x,0,z,Blocks.STONE);
    }

    @GameTest(maxTicks=100)
    public void registriesAndPlacement(GameTestHelper h) {
        for(String path:new String[]{"stormshard_sword","stormshard_gem","lightning_core","charged_ingot","storm_crystal_ore"})
            h.assertTrue(BuiltInRegistries.ITEM.containsKey(id(path)), "Missing item: " + path);
        var ore=BuiltInRegistries.BLOCK.get(id("storm_crystal_ore")).orElseThrow().value();
        h.assertTrue(ore!=Blocks.AIR,"Ore resolves to air");
        h.setBlock(2,1,2,ore);
        h.assertBlockPresent(ore,2,1,2);
        var access=h.getLevel().registryAccess();
        h.assertTrue(access.lookupOrThrow(Registries.CONFIGURED_FEATURE).get(ResourceKey.create(Registries.CONFIGURED_FEATURE,id("storm_crystal_ore"))).isPresent(),"Missing dynamic configured feature");
        h.assertTrue(access.lookupOrThrow(Registries.PLACED_FEATURE).get(ResourceKey.create(Registries.PLACED_FEATURE,id("storm_crystal_ore"))).isPresent(),"Missing dynamic placed feature");
        pass("registries_placement",h);
    }

    @GameTest(maxTicks=100)
    public void spawnAndAnimation(GameTestHelper h) {
        floor(h);
        var mob=h.spawnWithNoFreeWill(StudioMobTypes.STORMGUARDIAN,h.relativeVec(new Vec3(2.5,1,2.5)));
        h.assertTrue(mob.isAlive(),"Guardian must spawn alive");
        h.assertTrue(Math.abs(mob.getMaxHealth()-60)<.001,"Max health mismatch");
        h.assertTrue(Math.abs(mob.getAttributeValue(Attributes.ATTACK_DAMAGE)-8)<.001,"Attack attribute mismatch");
        h.assertTrue(Math.abs(mob.getAttributeValue(Attributes.MOVEMENT_SPEED)-.28)<.001,"Movement speed mismatch");
        h.assertTrue(mob.triggerStudioAnimation("walk"),"walk rejected");
        h.assertTrue(mob.getStudioAnimationId().equals("walk"),"walk ID mismatch");
        h.assertFalse(mob.triggerStudioAnimation("no_such_animation"),"Unknown animation accepted");
        h.assertTrue(mob.getStudioAnimationId().equals("walk"),"Invalid ID changed animation");
        pass("spawn_animation",h);
    }

    // Exercise generated Goal against real entities without scheduler nondeterminism.
    // A fresh second target avoids mistaking vanilla damage immunity for our cooldown.
    @GameTest(maxTicks=100)
    public void meleeAndCooldown(GameTestHelper h) {
        floor(h);
        var mob=h.spawnWithNoFreeWill(StudioMobTypes.STORMGUARDIAN,h.relativeVec(new Vec3(3.5,1,3.5)));
        var a=h.spawnWithNoFreeWill(EntityTypes.IRON_GOLEM,h.relativeVec(new Vec3(4.5,1,3.5)));
        var b=h.spawnWithNoFreeWill(EntityTypes.IRON_GOLEM,h.relativeVec(new Vec3(2.5,1,3.5)));
        h.assertTrue(mob.distanceToSqr(a)<2.6*2.6 && mob.distanceToSqr(b)<2.6*2.6,"Fixture targets out of range");
        var goal=new StormGuardianBehaviorGoal(mob);
        float hpA=a.getHealth(),hpB=b.getHealth();
        mob.setTarget(a);
        goal.tick();
        h.assertTrue(a.getHealth()<hpA,"Generated melee failed to damage first target");
        h.assertTrue(mob.getStudioAnimationId().equals("attack"),"Successful hit did not trigger attack animation");
        mob.setTarget(b);
        goal.tick();
        h.assertTrue(b.getHealth()==hpB,"Second fresh target damaged during cooldown");
        pass("melee_cooldown",h);
    }

    @GameTest(maxTicks=100)
    public void farTargetNotHit(GameTestHelper h) {
        floor(h);
        var mob=h.spawnWithNoFreeWill(StudioMobTypes.STORMGUARDIAN,h.relativeVec(new Vec3(1.5,1,1.5)));
        var target=h.spawnWithNoFreeWill(EntityTypes.IRON_GOLEM,h.relativeVec(new Vec3(6.5,1,6.5)));
        h.assertTrue(mob.distanceToSqr(target)>2.6*2.6,"Fixture target too close");
        float hp=target.getHealth();
        mob.setTarget(target);
        new StormGuardianBehaviorGoal(mob).tick();
        h.assertTrue(target.getHealth()==hp,"Out-of-range melee caused damage");
        pass("far_target",h);
    }
}
