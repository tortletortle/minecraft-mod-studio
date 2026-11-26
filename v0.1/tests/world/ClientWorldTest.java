package studio.acceptance;

import com.example.voidscout.ModEntities;
import com.example.voidscout.VoidScoutEntity;
import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import net.fabricmc.fabric.api.client.gametest.v1.context.TestSingleplayerContext;
import net.minecraft.client.gui.screens.worldselection.WorldCreationUiState;
import net.minecraft.core.BlockPos;

@SuppressWarnings("UnstableApiUsage")
public final class ClientWorldTest implements FabricClientGameTest {
    @Override
    public void runTest(ClientGameTestContext context) {
        context.getInput().resizeWindow(1280, 720);
        try (TestSingleplayerContext world = context.worldBuilder()
                .adjustSettings(creator -> creator.setGameMode(WorldCreationUiState.SelectedGameMode.CREATIVE))
                .create()) {
            world.getConnection().waitForChunksRender();

            var mob = world.getServer().computeOnServer(server -> {
                var level = world.getConnection().getServerLevel();
                var player = world.getConnection().getServerPlayer();
                var entity = new VoidScoutEntity(ModEntities.VOID_SCOUT, level);
                entity.setPos(player.getX(), player.getY(), player.getZ() + 3.0D);
                entity.setNoAi(true);
                if (!level.addFreshEntity(entity)) {
                    throw new AssertionError("Minecraft rejected the generated entity");
                }
                return entity;
            });

            var uuid = mob.getUUID();
            world.getConnection().waitForClientboundEntityUpdates(ModEntities.VOID_SCOUT);
            context.waitFor(client -> client.level != null && client.level.getEntity(uuid) instanceof VoidScoutEntity);
            context.getInput().lookAt(context.computeOnClient(client ->
                BlockPos.containing(client.level.getEntity(uuid).position().add(0, 1, 0))
            ));
            context.waitTicks(5);
            context.takeScreenshot("void_scout_spawned_and_rendered");

            if (!context.computeOnClient(client ->
                    client.level.getEntity(uuid) instanceof VoidScoutEntity)) {
                throw new AssertionError("Generated entity did not exist on the client");
            }

            System.out.println("MMS_V01_CLIENT_PASS client_entity_rendered");
        }
    }
}
