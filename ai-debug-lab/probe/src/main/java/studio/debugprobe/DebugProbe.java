package studio.debugprobe;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.MinecraftServer;
import org.slf4j.LoggerFactory;
import org.slf4j.Logger;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class DebugProbe implements ModInitializer {
    private static final Logger LOG = LoggerFactory.getLogger("mms-debug-probe");
    private static final Gson GSON = new Gson();
    private static final int PERIOD = 100;
    private static final int MAX_IDS = 20000;
    private final AtomicBoolean busy = new AtomicBoolean();
    private ExecutorService writer;
    private MinecraftServer active;
    private String session;
    private Path directory;
    private long ticks, windowStart;
    private BlockPos target;
    private JsonObject registrations;
    private boolean dedicated;

    @Override public void onInitialize() {
        // Explicit local opt-in. No listening socket, no command registration.
        if (!Boolean.getBoolean("mms.debug.enabled")) return;
        try {
            String pos = System.getProperty("mms.debug.overworld.pos", "0,80,0");
            String[] parts = pos.split(",", -1);
            if (parts.length != 3) throw new IllegalArgumentException("Expected x,y,z");
            int x=Integer.parseInt(parts[0]), y=Integer.parseInt(parts[1]), z=Integer.parseInt(parts[2]);
            if (Math.abs((long)x)>29999984 || Math.abs((long)z)>29999984 || y< -2048 || y>2048)
                throw new IllegalArgumentException("Position outside supported range");
            target=new BlockPos(x,y,z);
        } catch (RuntimeException e) {
            LOG.warn("MMS debug probe disabled: invalid coordinates");
            return;
        }
        ServerLifecycleEvents.SERVER_STARTED.register(this::started);
        ServerTickEvents.END_SERVER_TICK.register(this::tick);
        ServerLifecycleEvents.SERVER_STOPPING.register(this::stopping);
    }

    private void started(MinecraftServer server) {
        if (active != null) return;
        active=server;
        session=UUID.randomUUID().toString();
        ticks=0;
        windowStart=System.nanoTime();
        dedicated=server.isDedicatedServer();
        // Session-specific output prevents stale integrated-server snapshots being confused.
        directory=FabricLoader.getInstance().getGameDir().resolve("mms-debug").resolve(session);
        writer=Executors.newSingleThreadExecutor(r -> {
            Thread t=new Thread(r,"mms-debug-writer"); t.setDaemon(true); return t;
        });
        registrations=new JsonObject();
        JsonArray mods=new JsonArray();
        FabricLoader.getInstance().getAllMods().stream()
            .sorted(java.util.Comparator.comparing(m->m.getMetadata().getId()))
            .limit(MAX_IDS).forEach(m->{
                JsonObject row=new JsonObject();
                row.addProperty("id",m.getMetadata().getId());
                row.addProperty("version",m.getMetadata().getVersion().getFriendlyString());
                mods.add(row);
            });
        registrations.add("mods",mods);
        registrations.addProperty("mods_total",FabricLoader.getInstance().getAllMods().size());
        addRegistry("items",BuiltInRegistries.ITEM.keySet());
        addRegistry("blocks",BuiltInRegistries.BLOCK.keySet());
        addRegistry("entity_types",BuiltInRegistries.ENTITY_TYPE.keySet());
        addRegistry("block_entity_types",BuiltInRegistries.BLOCK_ENTITY_TYPE.keySet());
        LOG.info("MMS_DEBUG_SESSION {}",session);
    }
    private void addRegistry(String name, java.util.Collection<?> keys) {
        JsonArray rows=new JsonArray();
        keys.stream().map(Object::toString).sorted().limit(MAX_IDS).forEach(rows::add);
        registrations.add(name,rows);
        registrations.addProperty(name+"_total",keys.size());
    }
    private void tick(MinecraftServer server) {
        if (active!=server) return;
        ticks++;
        if (ticks%PERIOD!=0) return;
        long now=System.nanoTime(), elapsed=now-windowStart;
        windowStart=now;
        if (!busy.compareAndSet(false,true)) return;
        try {
            JsonObject out=new JsonObject();
            out.addProperty("schema",1); out.addProperty("session",session);
            out.addProperty("at",Instant.now().toString());
            out.addProperty("dedicated",dedicated);
            out.addProperty("tick_callbacks",ticks);
            out.addProperty("window_callbacks",PERIOD);
            out.addProperty("window_elapsed_ms",elapsed/1_000_000.0);
            out.addProperty("scope","read_only_loaded_overworld");
            out.add("registrations",registrations);
            JsonObject block=new JsonObject();
            block.addProperty("dimension","minecraft:overworld");
            block.addProperty("x",target.getX());block.addProperty("y",target.getY());block.addProperty("z",target.getZ());
            var level=server.overworld();
            var chunk=level.getChunkSource().getChunkNow(target.getX()>>4,target.getZ()>>4);
            if (chunk==null) block.addProperty("status","chunk_not_loaded");
            else {
                block.addProperty("status","observed");
                block.addProperty("id",BuiltInRegistries.BLOCK.getKey(chunk.getBlockState(target).getBlock()).toString());
                // CHECK only: do not create a block entity. No inventory or private NBT collected.
                var entity=chunk.getBlockEntity(target, net.minecraft.world.level.chunk.LevelChunk.EntityCreationType.CHECK);
                if (entity!=null) block.addProperty("block_entity_type",BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(entity.getType()).toString());
            }
            out.add("block",block);
            // Transfer immutable JSON string off the server thread for I/O.
            String text=GSON.toJson(out);
            Path dst=directory;
            writer.execute(()->{
                try {
                    Files.createDirectories(dst);
                    Path tmp=Files.createTempFile(dst,"snapshot-",".tmp");
                    try {
                        Files.writeString(tmp,text,StandardCharsets.UTF_8);
                        Files.move(tmp,dst.resolve("snapshot.json"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                    } finally {Files.deleteIfExists(tmp);}
                } catch (Exception e) {LOG.warn("MMS debug snapshot unavailable: {}",e.getClass().getSimpleName());}
                finally {busy.set(false);}
            });
        } catch (RuntimeException e) {
            busy.set(false);
            LOG.warn("MMS debug snapshot capture failed: {}",e.getClass().getSimpleName());
        }
    }
    private void stopping(MinecraftServer server) {
        if(active!=server)return;
        active=null;
        writer.shutdown();
        try { if(!writer.awaitTermination(2,TimeUnit.SECONDS)) writer.shutdownNow(); }
        catch(InterruptedException e){writer.shutdownNow();Thread.currentThread().interrupt();}
        writer=null;
    }
}
