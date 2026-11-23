package dev.mms.livedebugger;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.io.IOException;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.List;
import java.util.UUID;
import java.util.HexFormat;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.Entity;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.Identifier;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.Attribute;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * Command entry points are called on the Minecraft client thread.
 * World mutations are explicitly dispatched to the integrated-server thread.
 */
public final class PlayerController {
    private static final int MAX_MOVE_TICKS = 40;
    private static final int MAX_BLOCK_PATCH_PLACEMENTS = 32;
    private static final double MAX_BLOCK_PATCH_DISTANCE = 16.0;
    private static final long BLOCK_PATCH_PLAN_TTL_MS = 120_000L;
    private static final long BLOCK_PATCH_TRANSACTION_TTL_MS = 600_000L;
    private static final int MAX_PENDING_BLOCK_PATCHES = 8;
    private static final int MAX_ACTIVE_BLOCK_PATCHES = 4;
    private static final Set<String> UNSAFE_BLOCK_IDS = Set.of(
            "minecraft:tnt", "minecraft:fire", "minecraft:soul_fire", "minecraft:redstone_block",
            "minecraft:respawn_anchor", "minecraft:end_portal", "minecraft:nether_portal",
            "minecraft:end_gateway", "minecraft:lava", "minecraft:water", "minecraft:powder_snow",
            "minecraft:sand", "minecraft:red_sand", "minecraft:gravel",
            "minecraft:suspicious_sand", "minecraft:suspicious_gravel",
            "minecraft:anvil", "minecraft:chipped_anvil", "minecraft:damaged_anvil",
            "minecraft:dragon_egg");
    private static final double MAX_ENTITY_RADIUS = 32.0;
    private static final double MAX_BLOCK_DISTANCE = 64.0;
    private static final double MAX_ENTITY_CONTROL_DISTANCE = 64.0;
    private static final List<AttributeSpec> CONTROLLED_ATTRIBUTES = List.of(
            new AttributeSpec("max_health", Attributes.MAX_HEALTH, "MAX_HEALTH", 1.0, 1024.0),
            new AttributeSpec("attack_damage", Attributes.ATTACK_DAMAGE, "ATTACK_DAMAGE", 0.0, 256.0),
            new AttributeSpec("movement_speed", Attributes.MOVEMENT_SPEED, "MOVEMENT_SPEED", 0.0, 4.0));

    private final Map<String, PendingBlockPatch> pendingBlockPatches = new LinkedHashMap<>();
    private final Map<String, AppliedBlockPatch> appliedBlockPatches = new LinkedHashMap<>();
    private Movement movement;
    private volatile boolean screenshotCaptureActive;

    public void tick(Minecraft client) {
        if (movement == null) {
            return;
        }
        if (!isSinglePlayerWorld(client) || client.gui.screen() != null) {
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
            case "scene_snapshot" -> sceneSnapshot(client, request);
            case "capture_screenshot" -> captureScreenshot(client);
            case "move" -> move(client, request);
            case "look" -> look(client, request);
            case "stop" -> stopCommand(client);
            case "entities" -> entities(client, request);
            case "inspect_entity" -> inspectEntity(client, request);
            case "entity_attributes" -> entityAttributes(client, request);
            case "set_entity_attribute" -> setEntityAttribute(client, request);
            case "reset_entity_attributes" -> resetEntityAttributes(client, request);
            case "trigger_animation" -> triggerAnimation(client, request);
            case "block" -> inspectBlock(client, request);
            case "block_patch_preview" -> previewBlockPatch(client, request);
            case "block_patch_apply" -> applyBlockPatch(client, request);
            case "block_patch_rollback" -> rollbackBlockPatch(client, request);
            case "command_catalog" -> commandCatalog(client, request);
            case "command_inspect" -> commandInspect(client, request);
            case "command_validate" -> commandValidate(client, request);
            default -> throw new IllegalArgumentException("UNKNOWN_COMMAND");
        };
    }

    private JsonObject sceneSnapshot(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        double radius = boundedNumber(request, "radius", 16.0, 1.0, MAX_ENTITY_RADIUS);

        JsonObject result = status(client);
        JsonObject entityRequest = new JsonObject();
        entityRequest.addProperty("radius", radius);
        JsonObject entityResult = entities(client, entityRequest);
        result.add("nearby_entities", entityResult.get("entities").deepCopy());
        result.addProperty("entity_count", entityResult.get("returned").getAsInt());
        result.addProperty("entities_truncated", entityResult.get("truncated").getAsBoolean());

        JsonObject player = result.getAsJsonObject("player");
        int x = (int) Math.floor(player.get("x").getAsDouble());
        int y = (int) Math.floor(player.get("y").getAsDouble());
        int z = (int) Math.floor(player.get("z").getAsDouble());
        JsonObject blocks = new JsonObject();
        blocks.add("below_feet", blockAt(client, x, (int) Math.floor(player.get("y").getAsDouble() - 0.01), z));
        blocks.add("feet", blockAt(client, x, y, z));
        blocks.add("head", blockAt(client, x, (int) Math.floor(player.get("y").getAsDouble() + 1.62), z));
        result.add("nearby_blocks", blocks);
        result.addProperty("snapshot_consistency", "single_client_thread_capture");
        return result;
    }

    private JsonObject blockAt(Minecraft client, int x, int y, int z) {
        JsonObject request = new JsonObject();
        request.addProperty("x", x);
        request.addProperty("y", y);
        request.addProperty("z", z);
        return inspectBlock(client, request);
    }

    private JsonObject captureScreenshot(Minecraft client) {
        requireSinglePlayerWorld(client);
        Path directory = FabricLoader.getInstance().getConfigDir().resolve("mms-live-debugger");
        Path target = directory.resolve("capture.png");
        Path metadata = directory.resolve("capture.json");
        String captureId = UUID.randomUUID().toString();
        if (screenshotCaptureActive) {
            throw new IllegalStateException("SCREENSHOT_ALREADY_ACTIVE");
        }
        screenshotCaptureActive = true;

        try {
            if (Files.isSymbolicLink(directory) || Files.isSymbolicLink(target) || Files.isSymbolicLink(metadata)) {
                throw new IllegalStateException("SCREENSHOT_PATH_REJECTED");
            }
            Files.createDirectories(directory);
            Files.deleteIfExists(metadata);
        } catch (IOException exception) {
            screenshotCaptureActive = false;
            throw new IllegalStateException("SCREENSHOT_DIRECTORY_UNAVAILABLE");
        } catch (RuntimeException exception) {
            screenshotCaptureActive = false;
            throw exception;
        }

        // Screenshot readback completes asynchronously. Never wait on the client/render thread:
        // doing so can prevent the callback from running and freeze the game.
        try {
            Screenshot.takeScreenshot(client.gameRenderer.mainRenderTarget(), screenshot -> {
            int width = screenshot.getWidth();
            int height = screenshot.getHeight();
            CompletableFuture.runAsync(() -> {
                Path temporaryImage = directory.resolve("capture-" + captureId + ".tmp");
                Path temporaryMetadata = directory.resolve("capture-" + captureId + ".json.tmp");
                try (screenshot) {
                    if (Files.isSymbolicLink(directory) || Files.isSymbolicLink(target) || Files.isSymbolicLink(metadata)) {
                        throw new IOException("Screenshot destination changed to a symbolic link");
                    }
                    screenshot.writeToFile(temporaryImage);
                    try {
                        Files.move(temporaryImage, target,
                                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                    } catch (AtomicMoveNotSupportedException ignored) {
                        Files.move(temporaryImage, target, StandardCopyOption.REPLACE_EXISTING);
                    }

                    long imageSize = Files.size(target);
                    if (imageSize < 24 || imageSize > 8L * 1024L * 1024L) {
                        throw new IOException("Screenshot exceeds the 8 MiB protocol limit");
                    }
                    byte[] imageBytes = Files.readAllBytes(target);
                    JsonObject result = new JsonObject();
                    result.addProperty("capture_id", captureId);
                    result.addProperty("file_name", "capture.png");
                    result.addProperty("width", width);
                    result.addProperty("height", height);
                    result.addProperty("size_bytes", imageSize);
                    result.addProperty("sha256", HexFormat.of().formatHex(
                            MessageDigest.getInstance("SHA-256").digest(imageBytes)));
                    result.addProperty("captured_at_epoch_ms", System.currentTimeMillis());
                    Files.writeString(temporaryMetadata, result.toString());
                    try {
                        Files.move(temporaryMetadata, metadata,
                                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                    } catch (AtomicMoveNotSupportedException ignored) {
                        Files.move(temporaryMetadata, metadata, StandardCopyOption.REPLACE_EXISTING);
                    }
                    screenshotCaptureActive = false;
                } catch (Exception exception) {
                    try {
                        Files.deleteIfExists(temporaryImage);
                        Files.deleteIfExists(temporaryMetadata);
                    } catch (IOException ignored) {
                    }
                    try {
                        if (!Files.isSymbolicLink(directory) && !Files.isSymbolicLink(metadata)) {
                            JsonObject failure = new JsonObject();
                            failure.addProperty("capture_id", captureId);
                            failure.addProperty("error", "SCREENSHOT_CAPTURE_FAILED");
                            Files.writeString(metadata, failure.toString());
                        }
                    } catch (IOException ignored) {
                    }
                    screenshotCaptureActive = false;
                }
            });
            });
        } catch (RuntimeException exception) {
            screenshotCaptureActive = false;
            throw new IllegalStateException("SCREENSHOT_CAPTURE_UNAVAILABLE");
        }

        JsonObject accepted = new JsonObject();
        accepted.addProperty("capture_id", captureId);
        accepted.addProperty("file_name", "capture.png");
        accepted.addProperty("capture_requested", true);
        return accepted;
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



    private JsonObject previewBlockPatch(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        List<RequestedBlockPlacement> placements = parseBlockPlacements(request);
        ResourceKey<Level> dimension = client.level.dimension();
        UUID playerUuid = client.player.getUUID();

        return executeOnServer(client, server -> {
            ServerLevel level = server.getLevel(dimension);
            if (level == null) {
                throw new IllegalStateException("WORLD_NOT_AVAILABLE");
            }
            ServerPlayer player = requireCreativePatchPlayer(level, playerUuid);
            long now = System.currentTimeMillis();
            pruneBlockPatchState(now);
            if (pendingBlockPatches.size() >= MAX_PENDING_BLOCK_PATCHES) {
                throw new IllegalStateException("TOO_MANY_PENDING_BLOCK_PATCHES");
            }

            Set<BlockPos> uniquePositions = new HashSet<>();
            List<BlockPatchChange> changes = new ArrayList<>();
            for (RequestedBlockPlacement placement : placements) {
                BlockPos pos = placement.position();
                if (!uniquePositions.add(pos)) {
                    throw new IllegalArgumentException("DUPLICATE_BLOCK_PATCH_POSITION");
                }
                validatePatchPosition(level, player, pos);
                BlockState before = level.getBlockState(pos);
                if (!before.isAir()) {
                    throw new IllegalArgumentException("BLOCK_PATCH_TARGET_NOT_AIR");
                }
                if (level.getBlockEntity(pos) != null) {
                    throw new IllegalArgumentException("BLOCK_PATCH_BLOCK_ENTITY_NOT_SUPPORTED");
                }
                if (!placement.targetState().canSurvive(level, pos)) {
                    throw new IllegalArgumentException("BLOCK_PATCH_TARGET_CANNOT_SURVIVE");
                }
                changes.add(new BlockPatchChange(
                        pos, before, placement.targetState(), blockId(before), placement.targetId()));
            }

            String planId = UUID.randomUUID().toString();
            long expiresAt = now + BLOCK_PATCH_PLAN_TTL_MS;
            String snapshotHash = blockPatchSnapshotHash(dimension, changes);
            PendingBlockPatch plan = new PendingBlockPatch(
                    planId, server, dimension, playerUuid, expiresAt, List.copyOf(changes), snapshotHash);
            pendingBlockPatches.put(planId, plan);

            JsonObject result = new JsonObject();
            result.addProperty("plan_id", planId);
            result.addProperty("plan_status", "preview_ready");
            result.addProperty("world_dimension", dimension.toString());
            result.addProperty("placement_count", changes.size());
            result.addProperty("replacement_policy", "air_only");
            result.addProperty("block_state_properties_supported", false);
            result.addProperty("block_entities_supported", false);
            result.addProperty("snapshot_sha256", snapshotHash);
            result.addProperty("expires_at_epoch_ms", expiresAt);
            result.addProperty("expires_in_seconds", BLOCK_PATCH_PLAN_TTL_MS / 1000L);
            result.addProperty("execution_enabled", false);
            result.addProperty("world_state_simulated", false);
            result.add("placements", describeBlockPatch(changes));
            return result;
        });
    }

    private JsonObject applyBlockPatch(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        if (!optionalBoolean(request, "confirm", false)) {
            throw new IllegalArgumentException("CONFIRM_REQUIRED");
        }
        String planId = requiredString(request, "plan_id");
        ResourceKey<Level> dimension = client.level.dimension();
        UUID playerUuid = client.player.getUUID();

        return executeOnServer(client, server -> {
            long now = System.currentTimeMillis();
            pruneBlockPatchState(now);
            PendingBlockPatch plan = pendingBlockPatches.get(planId);
            if (plan == null || now > plan.expiresAtEpochMs()) {
                throw new IllegalArgumentException("BLOCK_PATCH_PLAN_EXPIRED_OR_NOT_FOUND");
            }
            if (plan.serverInstance() != server || !plan.dimension().equals(dimension)
                    || !plan.playerUuid().equals(playerUuid)) {
                throw new IllegalArgumentException("BLOCK_PATCH_PLAN_CONTEXT_MISMATCH");
            }
            if (appliedBlockPatches.size() >= MAX_ACTIVE_BLOCK_PATCHES) {
                throw new IllegalStateException("TOO_MANY_ACTIVE_BLOCK_PATCH_TRANSACTIONS");
            }

            ServerLevel level = server.getLevel(dimension);
            if (level == null) {
                throw new IllegalStateException("WORLD_NOT_AVAILABLE");
            }
            ServerPlayer player = requireCreativePatchPlayer(level, playerUuid);

            // Optimistic concurrency: no write occurs unless every captured pre-state still matches.
            for (BlockPatchChange change : plan.changes()) {
                validatePatchPosition(level, player, change.position());
                if (!level.getBlockState(change.position()).equals(change.beforeState())) {
                    throw new IllegalStateException("BLOCK_PATCH_STALE_WORLD_STATE");
                }
                if (level.getBlockEntity(change.position()) != null) {
                    throw new IllegalStateException("BLOCK_PATCH_BLOCK_ENTITY_APPEARED");
                }
                if (!change.targetState().canSurvive(level, change.position())) {
                    throw new IllegalStateException("BLOCK_PATCH_TARGET_NO_LONGER_SURVIVES");
                }
            }

            List<BlockPatchChange> changed = new ArrayList<>();
            for (BlockPatchChange change : plan.changes()) {
                boolean accepted = level.setBlock(change.position(), change.targetState(), 2);
                if (accepted || level.getBlockState(change.position()).equals(change.targetState())) {
                    changed.add(change);
                }
                if (!accepted || !level.getBlockState(change.position()).equals(change.targetState())) {
                    boolean restored = restoreBlockPatch(level, changed);
                    if (!restored) {
                        throw new IllegalStateException("BLOCK_PATCH_APPLY_FAILED_ROLLBACK_INCOMPLETE");
                    }
                    throw new IllegalStateException("BLOCK_PATCH_APPLY_FAILED_ROLLED_BACK");
                }
            }

            for (BlockPatchChange change : plan.changes()) {
                if (!level.getBlockState(change.position()).equals(change.targetState())) {
                    boolean restored = restoreBlockPatch(level, changed);
                    if (!restored) {
                        throw new IllegalStateException("BLOCK_PATCH_VERIFY_FAILED_ROLLBACK_INCOMPLETE");
                    }
                    throw new IllegalStateException("BLOCK_PATCH_VERIFY_FAILED_ROLLED_BACK");
                }
            }

            // Reuse the caller-known plan UUID so a lost apply response does not hide the rollback handle.
            String transactionId = plan.planId();
            long expiresAt = now + BLOCK_PATCH_TRANSACTION_TTL_MS;
            AppliedBlockPatch transaction = new AppliedBlockPatch(
                    transactionId, plan.planId(), server, dimension, playerUuid, expiresAt,
                    plan.changes(), plan.snapshotSha256());
            appliedBlockPatches.put(transactionId, transaction);
            pendingBlockPatches.remove(planId);

            JsonObject result = new JsonObject();
            result.addProperty("transaction_id", transactionId);
            result.addProperty("plan_id", plan.planId());
            result.addProperty("applied", true);
            result.addProperty("post_state_verified", true);
            result.addProperty("placement_count", plan.changes().size());
            result.addProperty("snapshot_sha256", plan.snapshotSha256());
            result.addProperty("rollback_available", true);
            result.addProperty("rollback_expires_at_epoch_ms", expiresAt);
            result.addProperty("execution_enabled", true);
            result.addProperty("execution_mode", "typed_block_state_api");
            result.addProperty("command_strings_executed", 0);
            return result;
        });
    }

    private JsonObject rollbackBlockPatch(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        if (!optionalBoolean(request, "confirm", false)) {
            throw new IllegalArgumentException("CONFIRM_REQUIRED");
        }
        String transactionId = requiredString(request, "transaction_id");
        ResourceKey<Level> dimension = client.level.dimension();
        UUID playerUuid = client.player.getUUID();

        return executeOnServer(client, server -> {
            long now = System.currentTimeMillis();
            pruneBlockPatchState(now);
            AppliedBlockPatch transaction = appliedBlockPatches.get(transactionId);
            if (transaction == null || now > transaction.expiresAtEpochMs()) {
                throw new IllegalArgumentException("BLOCK_PATCH_TRANSACTION_EXPIRED_OR_NOT_FOUND");
            }
            if (transaction.serverInstance() != server || !transaction.dimension().equals(dimension)
                    || !transaction.playerUuid().equals(playerUuid)) {
                throw new IllegalArgumentException("BLOCK_PATCH_TRANSACTION_CONTEXT_MISMATCH");
            }

            ServerLevel level = server.getLevel(dimension);
            if (level == null) {
                throw new IllegalStateException("WORLD_NOT_AVAILABLE");
            }
            ServerPlayer player = requirePatchPlayer(level, playerUuid);

            // All-or-none preflight: never overwrite a later player/mod edit.
            for (BlockPatchChange change : transaction.changes()) {
                validatePatchPosition(level, player, change.position());
                if (!level.getBlockState(change.position()).equals(change.targetState())) {
                    throw new IllegalStateException("BLOCK_PATCH_ROLLBACK_CONFLICT");
                }
                if (level.getBlockEntity(change.position()) != null) {
                    throw new IllegalStateException("BLOCK_PATCH_ROLLBACK_BLOCK_ENTITY_CONFLICT");
                }
            }

            List<BlockPatchChange> restored = new ArrayList<>();
            for (int index = transaction.changes().size() - 1; index >= 0; index--) {
                BlockPatchChange change = transaction.changes().get(index);
                boolean accepted = level.setBlock(change.position(), change.beforeState(), 2);
                if (accepted || level.getBlockState(change.position()).equals(change.beforeState())) {
                    restored.add(change);
                }
                if (!accepted || !level.getBlockState(change.position()).equals(change.beforeState())) {
                    boolean reapplied = reapplyBlockPatch(level, restored);
                    if (!reapplied) {
                        throw new IllegalStateException("BLOCK_PATCH_ROLLBACK_FAILED_COMPENSATION_INCOMPLETE");
                    }
                    throw new IllegalStateException("BLOCK_PATCH_ROLLBACK_FAILED_REAPPLIED");
                }
            }

            for (BlockPatchChange change : transaction.changes()) {
                if (!level.getBlockState(change.position()).equals(change.beforeState())) {
                    boolean reapplied = reapplyBlockPatch(level, restored);
                    if (!reapplied) {
                        throw new IllegalStateException("BLOCK_PATCH_ROLLBACK_VERIFY_FAILED_COMPENSATION_INCOMPLETE");
                    }
                    throw new IllegalStateException("BLOCK_PATCH_ROLLBACK_VERIFY_FAILED_REAPPLIED");
                }
            }

            appliedBlockPatches.remove(transactionId);
            JsonObject result = new JsonObject();
            result.addProperty("transaction_id", transactionId);
            result.addProperty("rolled_back", true);
            result.addProperty("restored_count", transaction.changes().size());
            result.addProperty("pre_state_verified", true);
            result.addProperty("snapshot_sha256", transaction.snapshotSha256());
            result.addProperty("execution_enabled", true);
            return result;
        });
    }

    private List<RequestedBlockPlacement> parseBlockPlacements(JsonObject request) {
        JsonElement raw = request.get("placements");
        if (raw == null || !raw.isJsonArray()) {
            throw new IllegalArgumentException("BLOCK_PATCH_PLACEMENTS_MUST_BE_ARRAY");
        }
        JsonArray array = raw.getAsJsonArray();
        if (array.size() == 0 || array.size() > MAX_BLOCK_PATCH_PLACEMENTS) {
            throw new IllegalArgumentException("BLOCK_PATCH_PLACEMENT_COUNT_OUT_OF_RANGE");
        }

        List<RequestedBlockPlacement> placements = new ArrayList<>();
        for (JsonElement element : array) {
            if (!element.isJsonObject()) {
                throw new IllegalArgumentException("BLOCK_PATCH_PLACEMENT_MUST_BE_OBJECT");
            }
            JsonObject item = element.getAsJsonObject();
            if (item.size() != 4 || !item.has("x") || !item.has("y")
                    || !item.has("z") || !item.has("block_id")) {
                throw new IllegalArgumentException("BLOCK_PATCH_PLACEMENT_FIELDS_INVALID");
            }
            int x = requiredStrictInteger(item, "x");
            int y = requiredStrictInteger(item, "y");
            int z = requiredStrictInteger(item, "z");
            String id = requiredString(item, "block_id");
            if (id.length() > 96 || !id.matches("[a-z0-9_.-]+:[a-z0-9_./-]+")) {
                throw new IllegalArgumentException("INVALID_BLOCK_ID");
            }
            if (!id.startsWith("minecraft:")) {
                throw new IllegalArgumentException("BLOCK_NAMESPACE_NOT_ALLOWED");
            }

            Identifier location;
            try {
                location = Identifier.parse(id);
            } catch (RuntimeException exception) {
                throw new IllegalArgumentException("INVALID_BLOCK_ID");
            }
            Block block = BuiltInRegistries.BLOCK.getOptional(location)
                    .orElseThrow(() -> new IllegalArgumentException("BLOCK_NOT_FOUND"));
            String registeredId = BuiltInRegistries.BLOCK.getKey(block).toString();
            if (!registeredId.equals(id)) {
                throw new IllegalArgumentException("BLOCK_ID_NOT_CANONICAL");
            }

            BlockState target = block.defaultBlockState();
            if (target.isAir() || target.hasBlockEntity() || !target.getFluidState().isEmpty()
                    || !target.isSolidRender() || isUnsafeBlockId(id)) {
                throw new IllegalArgumentException("BLOCK_TYPE_NOT_ALLOWED");
            }
            placements.add(new RequestedBlockPlacement(new BlockPos(x, y, z), target, id));
        }
        return placements;
    }

    private static boolean isUnsafeBlockId(String id) {
        return UNSAFE_BLOCK_IDS.contains(id)
                || id.endsWith("_concrete_powder")
                || id.endsWith("_shulker_box")
                || id.endsWith("_bed");
    }

    private static ServerPlayer requirePatchPlayer(ServerLevel level, UUID playerUuid) {
        Entity entity = level.getEntity(playerUuid);
        if (!(entity instanceof ServerPlayer player)) {
            throw new IllegalStateException("PLAYER_NOT_AVAILABLE");
        }
        return player;
    }

    private static ServerPlayer requireCreativePatchPlayer(ServerLevel level, UUID playerUuid) {
        ServerPlayer player = requirePatchPlayer(level, playerUuid);
        if (!player.isCreative()) {
            throw new IllegalStateException("CREATIVE_MODE_REQUIRED");
        }
        return player;
    }

    private static void validatePatchPosition(ServerLevel level, ServerPlayer player, BlockPos pos) {
        if (!level.isInWorldBounds(pos) || !level.hasChunkAt(pos)
                || !level.getWorldBorder().isWithinBounds(pos)) {
            throw new IllegalArgumentException("BLOCK_PATCH_POSITION_UNAVAILABLE");
        }
        if (player.distanceToSqr(pos.getX() + 0.5, pos.getY() + 0.5, pos.getZ() + 0.5)
                > MAX_BLOCK_PATCH_DISTANCE * MAX_BLOCK_PATCH_DISTANCE) {
            throw new IllegalArgumentException("BLOCK_PATCH_OUT_OF_RANGE");
        }
        AABB box = player.getBoundingBox();
        if (pos.getX() < box.maxX && pos.getX() + 1.0 > box.minX
                && pos.getY() < box.maxY && pos.getY() + 1.0 > box.minY
                && pos.getZ() < box.maxZ && pos.getZ() + 1.0 > box.minZ) {
            throw new IllegalArgumentException("BLOCK_PATCH_INTERSECTS_PLAYER");
        }
        AABB targetBox = new AABB(
                pos.getX(), pos.getY(), pos.getZ(),
                pos.getX() + 1.0, pos.getY() + 1.0, pos.getZ() + 1.0);
        if (!level.getEntities(player, targetBox).isEmpty()) {
            throw new IllegalArgumentException("BLOCK_PATCH_INTERSECTS_ENTITY");
        }
        if (!player.mayInteract(level, pos)) {
            throw new IllegalArgumentException("BLOCK_PATCH_PERMISSION_DENIED");
        }
    }

    private static JsonArray describeBlockPatch(List<BlockPatchChange> changes) {
        JsonArray placements = new JsonArray();
        for (BlockPatchChange change : changes) {
            JsonObject item = new JsonObject();
            item.addProperty("x", change.position().getX());
            item.addProperty("y", change.position().getY());
            item.addProperty("z", change.position().getZ());
            item.addProperty("before_block_id", change.beforeId());
            item.addProperty("target_block_id", change.targetId());
            placements.add(item);
        }
        return placements;
    }

    private static String blockId(BlockState state) {
        return BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
    }

    private static String blockPatchSnapshotHash(
            ResourceKey<Level> dimension, List<BlockPatchChange> changes) {
        StringBuilder canonical = new StringBuilder(dimension.toString());
        for (BlockPatchChange change : changes) {
            canonical.append('\n')
                    .append(change.position().getX()).append(',')
                    .append(change.position().getY()).append(',')
                    .append(change.position().getZ()).append('|')
                    .append(change.beforeId()).append('|')
                    .append(change.targetId());
        }
        try {
            return HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(
                            canonical.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA256_UNAVAILABLE");
        }
    }

    private void pruneBlockPatchState(long now) {
        pendingBlockPatches.entrySet().removeIf(entry -> now > entry.getValue().expiresAtEpochMs());
        appliedBlockPatches.entrySet().removeIf(entry -> now > entry.getValue().expiresAtEpochMs());
    }

    private static boolean restoreBlockPatch(ServerLevel level, List<BlockPatchChange> changes) {
        boolean restored = true;
        for (int index = changes.size() - 1; index >= 0; index--) {
            BlockPatchChange change = changes.get(index);
            level.setBlock(change.position(), change.beforeState(), 2);
            restored &= level.getBlockState(change.position()).equals(change.beforeState());
        }
        return restored;
    }

    private static boolean reapplyBlockPatch(ServerLevel level, List<BlockPatchChange> changes) {
        boolean reapplied = true;
        for (BlockPatchChange change : changes) {
            level.setBlock(change.position(), change.targetState(), 2);
            reapplied &= level.getBlockState(change.position()).equals(change.targetState());
        }
        return reapplied;
    }

    private JsonObject commandCatalog(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        ResourceKey<Level> dimension = client.level.dimension();
        double x = client.player.getX();
        double y = client.player.getY();
        double z = client.player.getZ();
        float pitch = client.player.getXRot();
        float yaw = client.player.getYRot();
        int offset = boundedInteger(request, "offset", 0, 0, 10_000);
        int limit = boundedInteger(request, "limit", 8, 1, 8);
        return executeOnServer(client, server -> AiCommandIntelligence.catalog(
                server, dimension, x, y, z, pitch, yaw, offset, limit));
    }

    private JsonObject commandInspect(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        ResourceKey<Level> dimension = client.level.dimension();
        double x = client.player.getX();
        double y = client.player.getY();
        double z = client.player.getZ();
        float pitch = client.player.getXRot();
        float yaw = client.player.getYRot();
        String name = requiredString(request, "name");
        return executeOnServer(client, server -> AiCommandIntelligence.inspect(
                server, dimension, x, y, z, pitch, yaw, name));
    }

    private JsonObject commandValidate(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        ResourceKey<Level> dimension = client.level.dimension();
        double x = client.player.getX();
        double y = client.player.getY();
        double z = client.player.getZ();
        float pitch = client.player.getXRot();
        float yaw = client.player.getYRot();
        String command = requiredString(request, "command");
        return executeOnServer(client, server -> AiCommandIntelligence.validate(
                server, dimension, x, y, z, pitch, yaw, command));
    }

    private JsonObject entityAttributes(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        UUID targetUuid = parseUuid(requiredString(request, "uuid"));
        ResourceKey<Level> dimension = client.level.dimension();
        UUID playerUuid = client.player.getUUID();

        return executeOnServer(client, server -> {
            Mob mob = requireStudioMob(server, dimension, playerUuid, targetUuid);
            JsonObject attributes = new JsonObject();
            for (AttributeSpec spec : CONTROLLED_ATTRIBUTES) {
                // The read-only accessors avoid creating/dirtying AttributeInstance objects.
                JsonObject value = new JsonObject();
                value.addProperty("available", true);
                value.addProperty("base", mob.getAttributeBaseValue(spec.attribute()));
                value.addProperty("effective", mob.getAttributeValue(spec.attribute()));
                value.addProperty("minimum", spec.minimum());
                value.addProperty("maximum", spec.maximum());
                attributes.add(spec.key(), value);
            }

            JsonObject result = new JsonObject();
            result.addProperty("uuid", mob.getUUID().toString());
            result.addProperty("type", BuiltInRegistries.ENTITY_TYPE.getKey(mob.getType()).toString());
            result.addProperty("health", mob.getHealth());
            result.addProperty("max_health", mob.getMaxHealth());
            result.add("attributes", attributes);
            result.addProperty("server_authoritative", true);
            return result;
        });
    }

    private JsonObject setEntityAttribute(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        UUID targetUuid = parseUuid(requiredString(request, "uuid"));
        String key = requiredString(request, "attribute");
        AttributeSpec spec = CONTROLLED_ATTRIBUTES.stream()
                .filter(candidate -> candidate.key().equals(key))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("ATTRIBUTE_NOT_ALLOWED"));
        double requestedValue = boundedNumber(
                request, "value", Double.NaN, spec.minimum(), spec.maximum());
        if (!optionalBoolean(request, "confirm", false)) {
            throw new IllegalArgumentException("CONFIRM_REQUIRED");
        }

        ResourceKey<Level> dimension = client.level.dimension();
        UUID playerUuid = client.player.getUUID();
        return executeOnServer(client, server -> {
            Mob mob = requireStudioMob(server, dimension, playerUuid, targetUuid);
            AttributeInstance instance = mob.getAttribute(spec.attribute());
            if (instance == null) {
                throw new IllegalArgumentException("ATTRIBUTE_NOT_SUPPORTED");
            }

            double previous = instance.getBaseValue();
            instance.setBaseValue(requestedValue);
            if ("max_health".equals(spec.key()) && mob.getHealth() > mob.getMaxHealth()) {
                mob.setHealth(mob.getMaxHealth());
            }

            JsonObject result = new JsonObject();
            result.addProperty("uuid", mob.getUUID().toString());
            result.addProperty("attribute", spec.key());
            result.addProperty("previous_base", previous);
            result.addProperty("new_base", instance.getBaseValue());
            result.addProperty("effective", instance.getValue());
            result.addProperty("health_after", mob.getHealth());
            result.addProperty("server_authoritative", true);
            return result;
        });
    }


    private JsonObject resetEntityAttributes(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        UUID targetUuid = parseUuid(requiredString(request, "uuid"));
        if (!optionalBoolean(request, "confirm", false)) {
            throw new IllegalArgumentException("CONFIRM_REQUIRED");
        }

        ResourceKey<Level> dimension = client.level.dimension();
        UUID playerUuid = client.player.getUUID();
        return executeOnServer(client, server -> {
            Mob mob = requireStudioMob(server, dimension, playerUuid, targetUuid);
            // Resolve and validate every generated default before mutating any attribute.
            List<PendingAttributeReset> pending = new ArrayList<>();
            for (AttributeSpec spec : CONTROLLED_ATTRIBUTES) {
                double generatedDefault = readGeneratedDefault(mob, spec);
                if (!Double.isFinite(generatedDefault)
                        || generatedDefault < spec.minimum()
                        || generatedDefault > spec.maximum()) {
                    throw new IllegalStateException("GENERATED_DEFAULT_OUT_OF_RANGE");
                }

                AttributeInstance instance = mob.getAttribute(spec.attribute());
                if (instance == null) {
                    throw new IllegalArgumentException("ATTRIBUTE_NOT_SUPPORTED");
                }
                pending.add(new PendingAttributeReset(
                        spec, instance, instance.getBaseValue(), generatedDefault));
            }

            JsonObject restored = new JsonObject();
            for (PendingAttributeReset reset : pending) {
                reset.instance().setBaseValue(reset.generatedDefault());
                JsonObject value = new JsonObject();
                value.addProperty("previous_base", reset.previousBase());
                value.addProperty("generated_default", reset.generatedDefault());
                value.addProperty("effective", reset.instance().getValue());
                restored.add(reset.spec().key(), value);
            }

            if (mob.getHealth() > mob.getMaxHealth()) {
                mob.setHealth(mob.getMaxHealth());
            }
            JsonObject result = new JsonObject();
            result.addProperty("uuid", mob.getUUID().toString());
            result.add("attributes", restored);
            result.addProperty("health_after", mob.getHealth());
            result.addProperty("reset_to_generated_defaults", true);
            result.addProperty("server_authoritative", true);
            return result;
        });
    }

    private static double readGeneratedDefault(Mob mob, AttributeSpec spec) {
        String entityClassName = mob.getClass().getName();
        if (!entityClassName.endsWith("Entity")) {
            throw new IllegalStateException("GENERATED_RIG_CLASS_NOT_FOUND");
        }
        String rigClassName = entityClassName.substring(0, entityClassName.length() - "Entity".length()) + "Rig";
        try {
            Class<?> rigClass = Class.forName(rigClassName, false, mob.getClass().getClassLoader());
            Field field = rigClass.getField(spec.defaultField());
            int modifiers = field.getModifiers();
            if (!Modifier.isStatic(modifiers)
                    || !Modifier.isFinal(modifiers)
                    || field.getType() != double.class) {
                throw new IllegalStateException("GENERATED_DEFAULT_FIELD_INVALID");
            }
            return field.getDouble(null);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("GENERATED_DEFAULTS_UNAVAILABLE");
        }
    }

    private JsonObject triggerAnimation(Minecraft client, JsonObject request) {
        requireSinglePlayerWorld(client);
        UUID targetUuid = parseUuid(requiredString(request, "uuid"));
        String animationId = requiredString(request, "animation_id");
        if (!animationId.matches("[A-Za-z0-9_.:-]{1,48}")) {
            throw new IllegalArgumentException("INVALID_ANIMATION_ID");
        }

        ResourceKey<Level> dimension = client.level.dimension();
        UUID playerUuid = client.player.getUUID();
        return executeOnServer(client, server -> {
            Mob mob = requireStudioMob(server, dimension, playerUuid, targetUuid);
            try {
                // The generator emits this one public method on its mob classes.
                // The method name and signature are fixed; no caller-supplied reflection is allowed.
                Method trigger = mob.getClass().getMethod("triggerStudioAnimation", String.class);
                Object accepted = trigger.invoke(mob, animationId);
                if (!Boolean.TRUE.equals(accepted)) {
                    throw new IllegalArgumentException("ANIMATION_NOT_FOUND");
                }
            } catch (NoSuchMethodException exception) {
                throw new IllegalArgumentException("ANIMATION_CONTROL_UNSUPPORTED");
            } catch (IllegalAccessException exception) {
                throw new IllegalStateException("ANIMATION_CONTROL_INACCESSIBLE");
            } catch (InvocationTargetException exception) {
                Throwable cause = exception.getCause();
                if (cause instanceof RuntimeException runtimeException) {
                    throw runtimeException;
                }
                throw new IllegalStateException("ANIMATION_TRIGGER_FAILED");
            }

            JsonObject result = new JsonObject();
            result.addProperty("uuid", mob.getUUID().toString());
            result.addProperty("animation_id", animationId);
            result.addProperty("triggered", true);
            result.addProperty("server_authoritative", true);
            return result;
        });
    }

    private Mob requireStudioMob(
            MinecraftServer server,
            ResourceKey<Level> dimension,
            UUID playerUuid,
            UUID targetUuid) {
        Mob mob = requireServerMob(server, dimension, playerUuid, targetUuid);
        try {
            // Every generated Studio mob exposes this fixed marker/control method.
            mob.getClass().getMethod("triggerStudioAnimation", String.class);
        } catch (NoSuchMethodException exception) {
            throw new IllegalArgumentException("STUDIO_MOB_REQUIRED");
        }
        return mob;
    }

    private Mob requireServerMob(
            MinecraftServer server,
            ResourceKey<Level> dimension,
            UUID playerUuid,
            UUID targetUuid) {
        ServerLevel level = server.getLevel(dimension);
        if (level == null) {
            throw new IllegalStateException("WORLD_NOT_AVAILABLE");
        }
        Entity serverPlayer = level.getEntity(playerUuid);
        if (serverPlayer == null) {
            throw new IllegalStateException("PLAYER_NOT_AVAILABLE");
        }
        Entity target = level.getEntity(targetUuid);
        if (!(target instanceof Mob mob) || mob.isRemoved()) {
            throw new IllegalArgumentException("MOB_NOT_FOUND");
        }
        if (!mob.isAlive()) {
            throw new IllegalArgumentException("MOB_NOT_ALIVE");
        }
        if (mob.distanceToSqr(serverPlayer) > MAX_ENTITY_CONTROL_DISTANCE * MAX_ENTITY_CONTROL_DISTANCE) {
            throw new IllegalArgumentException("ENTITY_OUT_OF_RANGE");
        }
        return mob;
    }

    private JsonObject executeOnServer(
            Minecraft client,
            java.util.function.Function<MinecraftServer, JsonObject> operation) {
        MinecraftServer server = client.getSingleplayerServer();
        if (server == null) {
            throw new IllegalStateException("SINGLEPLAYER_ONLY");
        }

        CompletableFuture<JsonObject> future = new CompletableFuture<>();
        server.execute(() -> {
            if (future.isCancelled()) {
                return;
            }
            try {
                future.complete(operation.apply(server));
            } catch (Throwable exception) {
                future.completeExceptionally(exception);
            }
        });

        try {
            return future.get(3, TimeUnit.SECONDS);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("SERVER_THREAD_INTERRUPTED");
        } catch (TimeoutException exception) {
            future.cancel(false);
            throw new IllegalStateException("SERVER_THREAD_TIMEOUT");
        } catch (ExecutionException exception) {
            Throwable cause = exception.getCause();
            if (cause instanceof RuntimeException runtimeException) {
                throw runtimeException;
            }
            throw new IllegalStateException("SERVER_COMMAND_FAILED");
        }
    }

    private static UUID parseUuid(String value) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException("INVALID_ENTITY_UUID");
        }
    }

    private record PendingAttributeReset(
            AttributeSpec spec,
            AttributeInstance instance,
            double previousBase,
            double generatedDefault) {}

    private record AttributeSpec(
            String key,
            Holder<Attribute> attribute,
            String defaultField,
            double minimum,
            double maximum) {}

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
        if (client.gui.screen() != null) {
            throw new IllegalStateException("GAME_SCREEN_NOT_ACTIVE");
        }
    }

    private static String requiredString(JsonObject object, String key) {
        if (!object.has(key) || !object.get(key).isJsonPrimitive() || !object.getAsJsonPrimitive(key).isString()) {
            throw new IllegalArgumentException("MISSING_OR_INVALID_" + key.toUpperCase());
        }
        return object.get(key).getAsString();
    }

    private static int requiredStrictInteger(JsonObject object, String key) {
        if (!object.has(key) || !object.get(key).isJsonPrimitive()
                || !object.getAsJsonPrimitive(key).isNumber()) {
            throw new IllegalArgumentException("MISSING_OR_INVALID_" + key.toUpperCase());
        }
        try {
            return object.getAsJsonPrimitive(key).getAsBigDecimal().intValueExact();
        } catch (ArithmeticException | NumberFormatException exception) {
            throw new IllegalArgumentException("MISSING_OR_INVALID_" + key.toUpperCase());
        }
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

    private record RequestedBlockPlacement(BlockPos position, BlockState targetState, String targetId) {}
    private record BlockPatchChange(
            BlockPos position, BlockState beforeState, BlockState targetState, String beforeId, String targetId) {}
    private record PendingBlockPatch(
            String planId, MinecraftServer serverInstance, ResourceKey<Level> dimension, UUID playerUuid,
            long expiresAtEpochMs, List<BlockPatchChange> changes, String snapshotSha256) {}
    private record AppliedBlockPatch(
            String transactionId, String planId, MinecraftServer serverInstance,
            ResourceKey<Level> dimension, UUID playerUuid, long expiresAtEpochMs,
            List<BlockPatchChange> changes, String snapshotSha256) {}

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
