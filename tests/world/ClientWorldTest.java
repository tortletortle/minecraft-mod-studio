package studio.acceptance;

import org.lwjgl.glfw.GLFW;
import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import net.fabricmc.fabric.api.client.gametest.v1.context.TestSingleplayerContext;
import net.minecraft.client.gui.screens.worldselection.WorldCreationUiState;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.client.model.geom.ModelPart;
import studio.generated.m_73746f726d73686172645f6d6f64.*;
import studio.generated.m_73746f726d73686172645f6d6f64.client.model.StormGuardianEntityModel;
import studio.generated.m_73746f726d73686172645f6d6f64.client.state.StormGuardianRenderState;

@SuppressWarnings("UnstableApiUsage")
public final class ClientWorldTest implements FabricClientGameTest {
    private static void verifyGeneratedLocomotionBlend() {
        ModelPart baked=StormGuardianEntityModel.createBodyLayer().bakeRoot();
        StormGuardianEntityModel model=new StormGuardianEntityModel(baked);
        StormGuardianRenderState state=new StormGuardianRenderState();
        state.ageInTicks=3.0F;
        state.walkAnimationSpeed=0.3F;
        state.studioAnimationId="walk";
        double weight=StormGuardianRig.locomotionBlend(state.walkAnimationSpeed,0.05,0.6);
        var idle=StormGuardianRig.poseAt("idle","leg_l",state.ageInTicks);
        var walk=StormGuardianRig.poseAt("walk","leg_l",state.ageInTicks);
        double expected=StormGuardianRig.blend(idle,walk,weight).rx();
        model.setupAnim(state);
        float actual=baked.getChild("root").getChild("leg_l").xRot;
        if(Math.abs(actual-expected)>0.0001) throw new AssertionError("Walk state bypassed locomotion blend: "+actual+" != "+expected);
        if(Math.abs(actual-walk.rx())<0.001) throw new AssertionError("Fixture blend weight did not distinguish the full walk clip");
        System.out.println("MMS_CLIENT_WORLD_PASS locomotion_blend weight="+weight+" leg_l="+actual);
    }

    @Override public void runTest(ClientGameTestContext context) {
        verifyGeneratedLocomotionBlend();
        context.getInput().resizeWindow(1280,720);
        context.takeScreenshot("title");
        try (TestSingleplayerContext world=context.worldBuilder()
                .adjustSettings(creator->creator.setGameMode(WorldCreationUiState.SelectedGameMode.CREATIVE)).create()) {
            world.getConnection().waitForChunksRender();
            world.getServer().runOnServer(server->{
                var level=world.getConnection().getServerLevel();
                for(int x=-5;x<=5;x++) for(int z=-5;z<=5;z++)
                    level.setBlock(new BlockPos(x,319,z),Blocks.STONE.defaultBlockState(),3);
                var player=world.getConnection().getServerPlayer();
                player.setPos(0.5,320,0.5);
                player.setYRot(0);
                player.setXRot(0);
            });
            context.waitTicks(10);
            context.getInput().pressKey(GLFW.GLFW_KEY_F1);
            context.waitTick();
            var mob=world.getServer().computeOnServer(server->{
                var level=world.getConnection().getServerLevel();
                var entity=new StormGuardianEntity(StudioMobTypes.STORMGUARDIAN,level);
                entity.snapTo(world.getConnection().getServerPlayer().position().add(0,0,2.5));
                entity.setYRot(180.0F);
                entity.setYHeadRot(180.0F);
                entity.setNoAi(true);
                if(!level.addFreshEntity(entity)) throw new AssertionError("Server spawn rejected");
                return entity;
            });
            var uuid=mob.getUUID();
            world.getConnection().waitForClientboundEntityUpdates(StudioMobTypes.STORMGUARDIAN);
            context.waitFor(client->client.level!=null && client.level.getEntity(uuid) instanceof StormGuardianEntity);
            var pos=context.computeOnClient(client->BlockPos.containing(client.level.getEntity(uuid).position().add(0,1,0)));
            context.getInput().lookAt(pos);
            context.waitTicks(3);
            context.takeScreenshot("guardian_idle");
            world.getServer().runOnServer(server->{
                if(!mob.triggerStudioAnimation("attack")) throw new AssertionError("Server rejected attack");
            });
            world.getConnection().waitForClientboundPackets();
            context.waitFor(client->client.level.getEntity(uuid) instanceof StormGuardianEntity e && e.getStudioAnimationId().equals("attack"));
            context.waitTicks(2);
            context.takeScreenshot("guardian_attack");
            System.out.println("MMS_CLIENT_WORLD_PASS spawn_attack_sync");
        }
    }
}
