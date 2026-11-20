package studio.conflictfixture;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Blocks;
public final class Beta implements ModInitializer {
    public void onInitialize() {
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            var level=server.overworld();
            var chunk=level.getChunkSource().getChunkNow(0,0);
            var trigger=new BlockPos(0,80,0);
            var output=new BlockPos(1,80,0);
            if(chunk!=null && chunk.getBlockState(trigger).is(Blocks.DIAMOND_BLOCK)
                && chunk.getBlockState(output).is(Blocks.RED_WOOL))
                level.setBlockAndUpdate(output,Blocks.OBSIDIAN.defaultBlockState());
        });
    }
}
