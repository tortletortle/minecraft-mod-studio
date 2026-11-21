package dev.mms.livedebugger;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.Vec3;

/**
 * All methods are called on the Minecraft client thread.
 * This first release intentionally supports only an integrated single-player world.
 */
public final class PlayerController {
    private static final int MAX_MOVE_TICKS = 40;
    private static final double MAX_ENTITY_RADIUS = 32.0;
    private static final double MAX_BLOCK_DISTANCE = 64.0;

    private Movement movement;

    public void tick(Minecraft client) {
        if (movement == null) {
            return;
        }
        if (!isSinglePlayerWorld(client) || client.screen != null) {
            stop(client);
            return;
        }

        applyMovementKeys(client, movement);
        movement.remainingTicks--;
        if (movement.remainingTicks <= 0) {
            stop(client);
        }
    }

    public void stop(Minecraft client) {
        boolean wasActive = movement != null;
        movement = null;
        if (wasActive) {
            releaseMovementKeys(client);
        }
    }

    public JsonObject execute(Minecraft client, JsonObject request) {
        String command = requiredString(request, "command");
        return switch (command) {
            case "status" -> status(client);
            case "move" -> move(client, request);
            case "look" -> look(client, request);
            case "stop" -> stopCommand(client);
            case "entities" -> entities(client, request);
            case "inspect_entity" -> inspectEntity(client, request);
            case "block" -> inspectBlock(client, request);
            default -> throw new IllegalArgumentException("UNKNOWN_COMMAND");
        };
    }

    private JsonObject status(Minecraft client) {
        requireSinglePlayerWorld(client);
        LocalPlayer player = client.player;
        Vec3 velocity = player.getDeltaMovement();

        JsonObject result = new JsonObject();
        result.addProperty("dimension", client.level.dimension().toString());
        result.addProperty("game_time", client.level.getGameTime());
        result.addProperty("movement_active", movement != null);
        JsonObject p = new JsonObject();
        p.addProperty("uuid", player.getUUID().toString());
        p.addProperty("name", player.getName().getString());
        p.addProperty("x", player.getX());
        p.addProperty("y", player.getY());
        p.addProperty("z", player.getZ());
        p.addProperty("yaw", player.getYRot());
        p.addProperty("pitch", player.getXRot());
        p.addProperty("health", player.getHealth());
        p.addProperty("max_health", player.getMaxHealth());
        p.addProperty("on_ground", player.onGround());
        p.addProperty("sprinting", player.isSprinting());
        p.addProperty("crouching", player.isCrouching());
        JsonObject v = new JsonObject();
        v.addProperty("x", velocity.x);
        v.addProperty("y", velocity.y);
        v.addProperty("z", velocity.z);
        p.add("velocity", v);
        result.add("player", p);
        return result;
    }

    private JsonObject move(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        if (movement != null) {
            throw new IllegalStateException("MOVEMENT_ALREADY_ACTIVE");
        }
        if (anyMovementKeyDown(client)) {
            throw new IllegalStateException("PLAYER_INPUT_BUSY");
        }

        double forward = boundedNumber(request, "forward", 0.0, -1.0, 1.0);
        double strafe = boundedNumber(request, "strafe", 0.0, -1.0, 1.0);
        int ticks = boundedInteger(request, "ticks", 10, 1, MAX_MOVE_TICKS);
        boolean jump = optionalBoolean(request, "jump", false);
        boolean sprint = optionalBoolean(request, "sprint", false);
        boolean sneak = optionalBoolean(request, "sneak", false);

        if (forward == 0.0 && strafe == 0.0 && !jump && !sprint && !sneak) {
            throw new IllegalArgumentException("EMPTY_MOVEMENT");
        }

        movement = new Movement(forward, strafe, jump, sprint, sneak, ticks);
        JsonObject result = new JsonObject();
        result.addProperty("accepted", true);
        result.addProperty("remaining_ticks", ticks);
        result.addProperty("max_ticks", MAX_MOVE_TICKS);
        return result;
    }

    private JsonObject look(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        double yaw = boundedNumber(request, "yaw", Double.NaN, -180.0, 180.0);
        double pitch = boundedNumber(request, "pitch", Double.NaN, -90.0, 90.0);
        client.player.setYRot((float) yaw);
        client.player.setXRot((float) pitch);

        JsonObject result = new JsonObject();
        result.addProperty("yaw", client.player.getYRot());
        result.addProperty("pitch", client.player.getXRot());
        return result;
    }

    private JsonObject stopCommand(Minecraft client) {
        stop(client);
        JsonObject result = new JsonObject();
        result.addProperty("stopped", true);
        return result;
    }

    private JsonObject entities(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        double radius = boundedNumber(request, "radius", 16.0, 1.0, MAX_ENTITY_RADIUS);
        double radiusSquared = radius * radius;
        List<Entity> nearby = new ArrayList<>();

        for (Entity entity : client.level.entitiesForRendering()) {
            if (entity == client.player || entity.isRemoved()) {
                continue;
            }
            if (entity.distanceToSqr(client.player) <= radiusSquared) {
                nearby.add(entity);
            }
        }

        nearby.sort(Comparator.comparingDouble(entity -> entity.distanceToSqr(client.player)));
        JsonArray values = new JsonArray();
        int limit = Math.min(nearby.size(), 50);
        for (int i = 0; i < limit; i++) {
            values.add(entitySummary(nearby.get(i), client.player));
        }

        JsonObject result = new JsonObject();
        result.addProperty("radius", radius);
        result.addProperty("returned", limit);
        result.addProperty("truncated", nearby.size() > limit);
        result.add("entities", values);
        return result;
    }

    private JsonObject inspectEntity(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        String rawUuid = requiredString(request, "uuid");
        UUID uuid;
        try {
            uuid = UUID.fromString(rawUuid);
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException("INVALID_ENTITY_UUID");
        }

        Entity entity = client.level.getEntity(uuid);
        if (entity == null || entity.isRemoved()) {
            throw new IllegalArgumentException("ENTITY_NOT_FOUND");
        }
        return entitySummary(entity, client.player);
    }

    private JsonObject inspectBlock(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        int x = requiredInteger(request, "x");
        int y = requiredInteger(request, "y");
        int z = requiredInteger(request, "z");
        BlockPos pos = new BlockPos(x, y, z);
        if (client.player.distanceToSqr(x + 0.5, y + 0.5, z + 0.5) > MAX_BLOCK_DISTANCE * MAX_BLOCK_DISTANCE) {
            throw new IllegalArgumentException("BLOCK_OUT_OF_RANGE");
        }

        BlockState state = client.level.getBlockState(pos);
        JsonObject result = new JsonObject();
        result.addProperty("x", x);
        result.addProperty("y", y);
        result.addProperty("z", z);
        result.addProperty("id", BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString());
        result.addProperty("name", state.getBlock().getName().getString());
        result.addProperty("fluid", !state.getFluidState().isEmpty());
        result.addProperty("air", state.isAir());
        return result;
    }

    private JsonObject entitySummary(Entity entity, LocalPlayer player) {
        Vec3 pos = entity.position();
        JsonObject result = new JsonObject();
        result.addProperty("uuid", entity.getUUID().toString());
        result.addProperty("entity_id", entity.getId());
        result.addProperty("type", BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()).toString());
        result.addProperty("name", entity.getName().getString());
        result.addProperty("x", pos.x);
        result.addProperty("y", pos.y);
        result.addProperty("z", pos.z);
        result.addProperty("distance", Math.sqrt(entity.distanceToSqr(player)));
        result.addProperty("alive", entity.isAlive());
        if (entity instanceof LivingEntity living) {
            result.addProperty("health", living.getHealth());
            result.addProperty("max_health", living.getMaxHealth());
        }
        return result;
    }

    private void applyMovementKeys(Minecraft client, Movement value) {
        client.options.keyUp.setDown(value.forward > 0.0);
        client.options.keyDown.setDown(value.forward < 0.0);
        client.options.keyRight.setDown(value.strafe > 0.0);
        client.options.keyLeft.setDown(value.strafe < 0.0);
        client.options.keyJump.setDown(value.jump);
        client.options.keySprint.setDown(value.sprint);
        client.options.keyShift.setDown(value.sneak);
    }

    private void releaseMovementKeys(Minecraft client) {
        client.options.keyUp.setDown(false);
        client.options.keyDown.setDown(false);
        client.options.keyRight.setDown(false);
        client.options.keyLeft.setDown(false);
        client.options.keyJump.setDown(false);
        client.options.keySprint.setDown(false);
        client.options.keyShift.setDown(false);
    }

    private boolean anyMovementKeyDown(Minecraft client) {
        return client.options.keyUp.isDown()
                || client.options.keyDown.isDown()
                || client.options.keyLeft.isDown()
                || client.options.keyRight.isDown()
                || client.options.keyJump.isDown()
                || client.options.keySprint.isDown()
                || client.options.keyShift.isDown();
    }

    private boolean isSinglePlayerWorld(Minecraft client) {
        return client.player != null && client.level != null && client.getSingleplayerServer() != null;
    }

    private void requireSinglePlayerWorld(Minecraft client) {
        if (client.player == null || client.level == null) {
            throw new IllegalStateException("NO_WORLD");
        }
        if (client.getSingleplayerServer() == null) {
            throw new IllegalStateException("SINGLEPLAYER_ONLY");
        }
        if (client.screen != null) {
            throw new IllegalStateException("GAME_SCREEN_NOT_ACTIVE");
        }
    }

    private static String requiredString(JsonObject object, String key) {
        if (!object.has(key) || !object.get(key).isJsonPrimitive() || !object.getAsJsonPrimitive(key).isString()) {
            throw new IllegalArgumentException("MISSING_OR_INVALID_" + key.toUpperCase());
        }
        return object.get(key).getAsString();
    }

    private static int requiredInteger(JsonObject object, String key) {
        if (!object.has(key) || !object.get(key).isJsonPrimitive()) {
            throw new IllegalArgumentException("MISSING_OR_INVALID_" + key.toUpperCase());
        }
        try {
            return object.get(key).getAsInt();
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException("MISSING_OR_INVALID_" + key.toUpperCase());
        }
    }

    private static int boundedInteger(JsonObject object, String key, int fallback, int min, int max) {
        int value = object.has(key) ? requiredInteger(object, key) : fallback;
        if (value < min || value > max) {
            throw new IllegalArgumentException("OUT_OF_RANGE_" + key.toUpperCase());
        }
        return value;
    }

    private static double boundedNumber(JsonObject object, String key, double fallback, double min, double max) {
        double value = object.has(key) ? object.get(key).getAsDouble() : fallback;
        if (!Double.isFinite(value) || value < min || value > max) {
            throw new IllegalArgumentException("OUT_OF_RANGE_" + key.toUpperCase());
        }
        return value;
    }

    private static boolean optionalBoolean(JsonObject object, String key, boolean fallback) {
        if (!object.has(key)) {
            return fallback;
        }
        if (!object.get(key).isJsonPrimitive() || !object.getAsJsonPrimitive(key).isBoolean()) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        return object.get(key).getAsBoolean();
    }

    private static final class Movement {
        private final double forward;
        private final double strafe;
        private final boolean jump;
        private final boolean sprint;
        private final boolean sneak;
        private int remainingTicks;

        private Movement(double forward, double strafe, boolean jump, boolean sprint, boolean sneak, int ticks) {
            this.forward = forward;
            this.strafe = strafe;
            this.jump = jump;
            this.sprint = sprint;
            this.sneak = sneak;
            this.remainingTicks = ticks;
        }
    }
}
