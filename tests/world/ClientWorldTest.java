package studio.acceptance;

import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import net.fabricmc.fabric.api.client.gametest.v1.context.TestSingleplayerContext;
import net.minecraft.client.gui.screens.worldselection.WorldCreationUiState;
import net.minecraft.core.BlockPos;
import studio.generated.m_73746f726d73686172645f6d6f64.*;

@SuppressWarnings("UnstableApiUsage")
public final class ClientWorldTest implements FabricClientGameTest {
    @Override public void runTest(ClientGameTestContext context) {
        context.takeScreenshot("title");
        try (TestSingleplayerContext world=context.worldBuilder()
                .adjustSettings(creator->creator.setGameMode(WorldCreationUiState.SelectedGameMode.CREATIVE)).create()) {
            world.getConnection().waitForChunksRender();
            world.getServer().runCommand("fill -5 319 -5 5 319 5 minecraft:stone");
            world.getServer().runCommand("tp @a 0.5 320 0.5 0 0");
            world.getServer().runCommand("time set noon");
            context.waitTicks(10);
            var mob=world.getServer().computeOnServer(server->{
                var level=world.getConnection().getServerLevel();
                var entity=new StormGuardianEntity(StudioMobTypes.STORMGUARDIAN,level);
                entity.snapTo(world.getConnection().getServerPlayer().position().add(0,0,3));
                entity.setNoAi(true);
                if(!level.addFreshEntity(entity)) throw new AssertionError("Server spawn rejected");
                return entity;
            });
            var uuid=mob.getUUID();
            world.getConnection().waitForClientboundEntityUpdates(StudioMobTypes.STORMGUARDIAN);
            context.waitFor(client->client.level!=null && client.level.getEntity(uuid) instanceof StormGuardianEntity);
            var pos=context.computeOnClient(client->BlockPos.containing(client.level.getEntity(uuid).position().add(0,1,0)));
            context.getInput().lookAt(pos);
            context.waitTicks(10);
            context.takeScreenshot("guardian_idle");
            world.getServer().runOnServer(server->{
                if(!mob.triggerStudioAnimation("walk")) throw new AssertionError("Server rejected walk");
            });
            world.getConnection().waitForClientboundPackets();
            context.waitFor(client->client.level.getEntity(uuid) instanceof StormGuardianEntity e && e.getStudioAnimationId().equals("walk"));
            context.takeScreenshot("guardian_walk");
            System.out.println("MMS_CLIENT_WORLD_PASS spawn_and_loop_sync");
        }
    }
}
