package studio.conflictfixture;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.world.level.block.Blocks;
public final class Alpha implements ModInitializer {
    public void onInitialize() {
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            var level=server.overworld();
            var chunk=level.getChunkSource().getChunkNow(0,0);
            if(chunk!=null && chunk.getBlockState(Positions.TRIGGER).is(Blocks.DIAMOND_BLOCK)
                && chunk.getBlockState(Positions.OUTPUT).is(Blocks.WHITE_WOOL))
                level.setBlockAndUpdate(Positions.OUTPUT,Blocks.RED_WOOL.defaultBlockState());
        });
    }
}
