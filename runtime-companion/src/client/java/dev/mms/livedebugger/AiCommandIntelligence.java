package dev.mms.livedebugger;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.ParseResults;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.tree.CommandNode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import net.minecraft.commands.CommandSource;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.permissions.PermissionSet;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec2;
import net.minecraft.world.phys.Vec3;

/**
 * Read-only discovery and validation against the live integrated-server Brigadier tree.
 *
 * The MMS operator is a named, non-player command source. Its ALL_PERMISSIONS view is
 * used only to discover the complete command tree and parse syntax in this prototype.
 * No method in this class executes a parsed command.
 */
public final class AiCommandIntelligence {
    private static final int MAX_CATALOG_LIMIT = 8;
    private static final int MAX_CATALOG_OFFSET = 10_000;
    private static final int MAX_INSPECT_ITEMS = 8;
    private static final int MAX_USAGE_LENGTH = 120;
    private static final int MAX_COMMAND_LENGTH = 512;

    private AiCommandIntelligence() {}

    public static JsonObject catalog(
            MinecraftServer server,
            ResourceKey<Level> dimension,
            double x,
            double y,
            double z,
            float pitch,
            float yaw,
            int offset,
            int limit) {
        if (offset < 0 || offset > MAX_CATALOG_OFFSET) {
            throw new IllegalArgumentException("OUT_OF_RANGE_OFFSET");
        }
        if (limit < 1 || limit > MAX_CATALOG_LIMIT) {
            throw new IllegalArgumentException("OUT_OF_RANGE_LIMIT");
        }

        CommandDispatcher<CommandSourceStack> dispatcher = server.getCommands().getDispatcher();
        CommandSourceStack source = createOperatorSource(server, dimension, x, y, z, pitch, yaw);
        CommandManifestRegistry.Registry manifests = CommandManifestRegistry.load(server, source);
        List<CommandNode<CommandSourceStack>> commands = dispatcher.getRoot().getChildren().stream()
                .filter(node -> node.canUse(source))
                .sorted(Comparator.comparing(CommandNode::getName))
                .toList();

        JsonArray entries = new JsonArray();
        int end = Math.min(commands.size(), offset + limit);
        for (int index = offset; index < end; index++) {
            CommandNode<CommandSourceStack> node = commands.get(index);
            JsonObject entry = new JsonObject();
            entry.addProperty("name", node.getName());
            entry.addProperty("executable_at_root", node.getCommand() != null);
            entry.addProperty("child_count", node.getChildren().stream().filter(child -> child.canUse(source)).count());
            entry.addProperty("redirect", node.getRedirect() != null);
            JsonObject manifest = manifests.manifestsByRoot().get(node.getName());
            if (manifest != null) {
                entry.add("manifest_summary", CommandManifestRegistry.searchSummary(manifest));
            }
            entries.add(entry);
        }

        JsonObject result = new JsonObject();
        result.addProperty("operator_id", "MMS_AI_OPERATOR");
        result.addProperty("operator_entity_bound", false);
        result.addProperty("permission_view", "ALL_PERMISSIONS");
        result.addProperty("execution_enabled", false);
        result.addProperty("dimension", dimension.location().toString());
        result.addProperty("total", commands.size());
        result.addProperty("offset", offset);
        result.addProperty("limit", limit);
        result.addProperty("has_more", end < commands.size());
        result.add("commands", entries);
        result.addProperty("catalog_source", "live_integrated_server_brigadier_dispatcher");
        result.addProperty("manifest_source", CommandManifestRegistry.RESOURCE_PATH);
        result.addProperty("manifest_file_count", manifests.manifestFileCount());
        result.addProperty("manifest_command_count", manifests.manifestCommandCount());
        result.addProperty("manifest_scanned_mods", manifests.scannedMods());
        result.add("manifest_issues", manifests.issues().deepCopy());
        result.addProperty("manifest_issue_count", manifests.issues().size());
        return result;
    }

    public static JsonObject inspect(
            MinecraftServer server,
            ResourceKey<Level> dimension,
            double x,
            double y,
            double z,
            float pitch,
            float yaw,
            String requestedName) {
        String name = normalizeRootName(requestedName);
        CommandDispatcher<CommandSourceStack> dispatcher = server.getCommands().getDispatcher();
        CommandSourceStack source = createOperatorSource(server, dimension, x, y, z, pitch, yaw);
        CommandManifestRegistry.Registry manifests = CommandManifestRegistry.load(server, source);
        CommandNode<CommandSourceStack> node = dispatcher.getRoot().getChild(name);
        if (node == null || !node.canUse(source)) {
            throw new IllegalArgumentException("COMMAND_NOT_FOUND_OR_NOT_VISIBLE");
        }

        String[] allUsage = dispatcher.getAllUsage(node, source, true);
        Map<CommandNode<CommandSourceStack>, String> smartUsage = dispatcher.getSmartUsage(node, source);

        JsonArray usages = new JsonArray();
        int usageCount = Math.min(allUsage.length, MAX_INSPECT_ITEMS);
        for (int index = 0; index < usageCount; index++) {
            usages.add(truncate(allUsage[index].isEmpty() ? name : name + " " + allUsage[index], MAX_USAGE_LENGTH));
        }

        JsonArray smart = new JsonArray();
        smartUsage.entrySet().stream()
                .sorted(Map.Entry.comparingByValue())
                .limit(MAX_INSPECT_ITEMS)
                .forEach(entry -> smart.add(truncate(name + " " + entry.getValue(), MAX_USAGE_LENGTH)));

        List<CommandNode<CommandSourceStack>> children = node.getChildren().stream()
                .filter(child -> child.canUse(source))
                .collect(java.util.stream.Collectors.toCollection(ArrayList::new));
        children.sort(Comparator.comparing(CommandNode::getName));
        JsonArray childEntries = new JsonArray();
        for (CommandNode<CommandSourceStack> child : children.stream().limit(MAX_INSPECT_ITEMS).toList()) {
            JsonObject item = new JsonObject();
            item.addProperty("name", truncate(child.getName(), 96));
            item.addProperty("node_type", child.getClass().getSimpleName());
            item.addProperty("executable", child.getCommand() != null);
            item.addProperty("child_count", child.getChildren().size());
            item.addProperty("redirect", child.getRedirect() != null);
            childEntries.add(item);
        }

        JsonObject result = new JsonObject();
        result.addProperty("operator_id", "MMS_AI_OPERATOR");
        result.addProperty("execution_enabled", false);
        result.addProperty("command", name);
        result.addProperty("executable_at_root", node.getCommand() != null);
        result.addProperty("child_count", children.size());
        result.addProperty("smart_usage_count", smartUsage.size());
        result.addProperty("smart_usage_truncated", smartUsage.size() > MAX_INSPECT_ITEMS);
        result.addProperty("redirect", node.getRedirect() != null);
        result.addProperty("usage_count", allUsage.length);
        result.addProperty("usages_truncated", allUsage.length > MAX_INSPECT_ITEMS);
        result.add("usages", usages);
        result.add("smart_usage", smart);
        result.add("children", childEntries);
        result.addProperty("children_truncated", children.size() > MAX_INSPECT_ITEMS);
        result.addProperty("catalog_source", "live_integrated_server_brigadier_dispatcher");
        JsonObject manifest = manifests.manifestsByRoot().get(name);
        result.addProperty("manifest_present", manifest != null);
        if (manifest != null) {
            result.add("manifest", manifest.deepCopy());
        }
        result.addProperty("manifest_file_count", manifests.manifestFileCount());
        result.addProperty("manifest_command_count", manifests.manifestCommandCount());
        result.addProperty("manifest_scanned_mods", manifests.scannedMods());
        result.add("manifest_issues", manifests.issues().deepCopy());
        result.addProperty("manifest_issue_count", manifests.issues().size());
        return result;
    }

    public static JsonObject validate(
            MinecraftServer server,
            ResourceKey<Level> dimension,
            double x,
            double y,
            double z,
            float pitch,
            float yaw,
            String requestedCommand) {
        String command = requestedCommand == null ? "" : requestedCommand.trim();
        if (command.startsWith("/")) {
            command = command.substring(1);
        }
        if (command.isBlank() || command.length() > MAX_COMMAND_LENGTH
                || command.indexOf('\n') >= 0 || command.indexOf('\r') >= 0
                || command.indexOf('\0') >= 0) {
            throw new IllegalArgumentException("INVALID_COMMAND_INPUT");
        }

        CommandDispatcher<CommandSourceStack> dispatcher = server.getCommands().getDispatcher();
        CommandSourceStack source = createOperatorSource(server, dimension, x, y, z, pitch, yaw);
        ParseResults<CommandSourceStack> parsed = dispatcher.parse(command, source);

        JsonObject result = new JsonObject();
        result.addProperty("operator_id", "MMS_AI_OPERATOR");
        result.addProperty("execution_enabled", false);
        result.addProperty("syntax_only", true);
        result.addProperty("command", command);
        result.addProperty("parsed_characters", parsed.getReader().getCursor());

        try {
            Commands.validateParseResults(parsed);
            if (parsed.getContext().getLastChild().getCommand() == null) {
                result.addProperty("valid", false);
                result.addProperty("error_code", "COMMAND_NOT_EXECUTABLE");
                result.addProperty("message", "The input ends before an executable command branch.");
                return result;
            }
            result.addProperty("valid", true);
            result.addProperty("error_code", "");
            result.addProperty("message", "Brigadier parsed an executable command path. No command was executed.");
        } catch (CommandSyntaxException exception) {
            result.addProperty("valid", false);
            result.addProperty("error_code", "COMMAND_SYNTAX_INVALID");
            result.addProperty("message", exception.getMessage());
            result.addProperty("error_cursor", exception.getCursor());
            if (exception.getInput() != null) {
                result.addProperty("error_input", exception.getInput());
            }
        }
        return result;
    }

    private static CommandSourceStack createOperatorSource(
            MinecraftServer server,
            ResourceKey<Level> dimension,
            double x,
            double y,
            double z,
            float pitch,
            float yaw) {
        ServerLevel level = server.getLevel(dimension);
        if (level == null) {
            throw new IllegalStateException("WORLD_NOT_AVAILABLE");
        }
        return new CommandSourceStack(
                CommandSource.NULL,
                new Vec3(x, y, z),
                new Vec2(pitch, yaw),
                level,
                PermissionSet.ALL_PERMISSIONS,
                "MMS_AI_OPERATOR",
                Component.literal("MMS AI Operator"),
                server,
                null);
    }

    private static String truncate(String value, int maximumLength) {
        if (value.length() <= maximumLength) {
            return value;
        }
        return value.substring(0, maximumLength - 1) + "…";
    }

    private static String normalizeRootName(String requestedName) {
        String name = requestedName == null ? "" : requestedName.trim();
        if (name.startsWith("/")) {
            name = name.substring(1);
        }
        if (name.isBlank() || name.length() > 64 || name.contains(" ")
                || name.indexOf('\n') >= 0 || name.indexOf('\r') >= 0) {
            throw new IllegalArgumentException("INVALID_COMMAND_NAME");
        }
        return name;
    }
}
