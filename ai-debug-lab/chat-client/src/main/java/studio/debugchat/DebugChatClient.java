package studio.debugchat;

import com.google.gson.JsonObject;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.command.v2.FabricClientCommandSource;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.HitResult;

import static net.fabricmc.fabric.api.client.command.v2.ClientCommands.argument;
import static net.fabricmc.fabric.api.client.command.v2.ClientCommands.literal;

public final class DebugChatClient implements ClientModInitializer {
    private static final String PREFIX = "[MMS] ";
    private final LocalBridge bridge = new LocalBridge();
    private boolean waiting;

    @Override
    public void onInitializeClient() {
        ClientCommandRegistrationCallback.EVENT.register((dispatcher, registryAccess) ->
                dispatcher.register(literal("mms").then(literal("ask")
                        .executes(ctx -> error(ctx.getSource(), "用法 /mms ask <问题>"))
                        .then(argument("question", StringArgumentType.greedyString())
                                .executes(ctx -> ask(ctx.getSource(), StringArgumentType.getString(ctx, "question")))))));
    }

    private int ask(FabricClientCommandSource source, String rawQuestion) {
        if (!source.attended()) {
            return error(source, "请从聊天框主动输入 /mms ask。");
        }
        var client = source.getClient();
        var server = client.getSingleplayerServer();
        var level = client.level;
        var player = client.player;
        if (server == null || server.isPublished() || level == null || player == null) {
            return error(source, "请先进入一个未向局域网开放的单人世界。");
        }
        String question = rawQuestion.strip();
        if (question.isBlank() || question.codePointCount(0, question.length()) > 320
                || question.codePoints().anyMatch(Character::isISOControl)) {
            return error(source, "请输入 1 至 320 个字符的单行问题。");
        }
        if (waiting) {
            return error(source, "上一条诊断还在处理，请稍等。");
        }
        var held = player.getMainHandItem();
        var heldEvidence = new JsonObject();
        heldEvidence.addProperty("id", BuiltInRegistries.ITEM.getKey(held.getItem()).toString());
        heldEvidence.addProperty("count", held.getCount());

        var evidence = new JsonObject();
        evidence.addProperty("dimension", level.dimension().identifier().toString());
        evidence.add("held", heldEvidence);
        var target = new JsonObject();
        switch (client.hitResult) {
            case BlockHitResult block when block.getType() == HitResult.Type.BLOCK -> {
                BlockState state = level.getBlockState(block.getBlockPos());
                var properties = new JsonObject();
                for (Property<?> property : state.getProperties()) {
                    properties.addProperty(property.getName(), propertyName(state, property));
                }
                target.addProperty("kind", "block");
                target.addProperty("id", BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString());
                target.add("properties", properties);
                evidence.addProperty("requires_correct_tool_for_drops", state.requiresCorrectToolForDrops());
                evidence.addProperty("held_item_correct_for_drops", held.isCorrectToolForDrops(state));
            }
            case EntityHitResult entity -> {
                target.addProperty("kind", "entity");
                target.addProperty("id", BuiltInRegistries.ENTITY_TYPE.getKey(entity.getEntity().getType()).toString());
            }
            case null, default -> target.addProperty("kind", "miss");
        }
        evidence.add("target", target);
        var request = new JsonObject();
        request.addProperty("question", question);
        request.add("context", evidence);

        var connection = client.getConnection();
        waiting = true;
        source.sendFeedback(Component.literal(PREFIX + "正在读取证据并诊断…"));
        bridge.diagnose(client.gameDirectory.toPath(), request).whenComplete((result, failure) ->
                client.execute(() -> {
                    waiting = false;
                    if (client.level != level || client.getConnection() != connection || server.isPublished()) {
                        return;
                    }
                    if (failure != null) {
                        error(source, "本地诊断请求失败，请检查桥接服务后重试。");
                    } else if (result.success()) {
                        source.sendFeedback(Component.literal(PREFIX + result.message()));
                    } else {
                        error(source, result.message());
                    }
                }));
        return 1;
    }

    private static <T extends Comparable<T>> String propertyName(BlockState state, Property<T> property) {
        return property.getName(state.getValue(property));
    }

    private static int error(FabricClientCommandSource source, String message) {
        source.sendError(Component.literal(PREFIX + message));
        return 0;
    }
}
