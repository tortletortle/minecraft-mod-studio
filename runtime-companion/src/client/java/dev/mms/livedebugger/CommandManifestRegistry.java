package dev.mms.livedebugger;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;
import net.fabricmc.loader.api.FabricLoader;
import net.fabricmc.loader.api.ModContainer;
import net.fabricmc.loader.api.metadata.ModMetadata;
import net.minecraft.server.MinecraftServer;
import net.minecraft.commands.CommandSourceStack;
import com.mojang.brigadier.tree.CommandNode;

/**
 * Loads bounded, descriptive command manifests from Fabric mod resources.
 *
 * A manifest is untrusted metadata, not executable code, command authorization,
 * proof of command ownership, or a source of agent instructions.
 */
public final class CommandManifestRegistry {
    public static final String RESOURCE_PATH = "mms/commands.json";
    private static final int SCHEMA_VERSION = 1;
    private static final long MAX_FILE_BYTES = 64 * 1024;
    private static final int MAX_MODS = 512;
    private static final int MAX_COMMANDS_PER_MOD = 64;
    private static final int MAX_TOTAL_COMMANDS = 512;
    private static final int MAX_KEYWORDS = 32;
    private static final int MAX_EXAMPLES = 8;
    private static final int MAX_ARGUMENTS = 32;
    private static final int MAX_ISSUES = 32;
    private static final Pattern ROOT_PATTERN = Pattern.compile("[a-z0-9_.:-]{1,64}");
    private static final Pattern LOCALE_PATTERN = Pattern.compile("[a-z]{2}_[a-z]{2}");
    private static final Pattern VERSION_PATTERN = Pattern.compile("[0-9][A-Za-z0-9._+-]{0,31}");

    private static final Set<String> TOP_LEVEL_FIELDS = Set.of(
            "schemaVersion", "modId", "modVersion", "minecraftVersions", "commands");
    private static final Set<String> COMMAND_FIELDS = Set.of(
            "root", "descriptions", "keywords", "examples", "argumentDescriptions",
            "effects", "executionContext", "advisoryRisk", "advisoryReversibility");
    private static final Set<String> EFFECTS = Set.of(
            "blocks", "entities", "inventory", "world_rules", "time_weather",
            "player_state", "server_state", "structures", "unknown");
    private static final Set<String> EXECUTION_CONTEXTS = Set.of("server", "player", "entity");
    private static final Set<String> RISKS = Set.of("read_only", "bounded_mutation", "destructive", "unknown");
    private static final Set<String> REVERSIBILITY = Set.of(
            "reversible", "partially_reversible", "irreversible", "unknown");

    private CommandManifestRegistry() {}

    public record Registry(
            Map<String, JsonObject> manifestsByRoot,
            JsonArray issues,
            int scannedMods,
            int manifestFileCount,
            int manifestCommandCount) {}

    public static Registry load(MinecraftServer server, CommandSourceStack source) {
        Set<String> liveRoots = new HashSet<>();
        for (CommandNode<CommandSourceStack> node : server.getCommands().getDispatcher().getRoot().getChildren()) {
            if (node.canUse(source)) {
                liveRoots.add(node.getName());
            }
        }

        Collection<ModContainer> loadedMods = FabricLoader.getInstance().getAllMods();
        List<ModContainer> mods = loadedMods.stream()
                .sorted(Comparator.comparing(mod -> mod.getMetadata().getId()))
                .limit(MAX_MODS)
                .toList();

        Map<String, JsonObject> manifests = new LinkedHashMap<>();
        Set<String> conflictingRoots = new HashSet<>();
        JsonArray issues = new JsonArray();
        int manifestFiles = 0;

        for (ModContainer mod : mods) {
            ModMetadata metadata = mod.getMetadata();
            Optional<Path> resource;
            try {
                resource = mod.findPath(RESOURCE_PATH);
            } catch (RuntimeException exception) {
                addIssue(issues, metadata.getId(), "RESOURCE_LOOKUP_FAILED");
                continue;
            }
            if (resource.isEmpty()) {
                continue;
            }
            manifestFiles++;
            if (manifestFiles > MAX_MODS) {
                addIssue(issues, metadata.getId(), "MANIFEST_COUNT_LIMIT_REACHED");
                break;
            }

            try {
                Path path = resource.get();
                long size = Files.size(path);
                if (size < 1 || size > MAX_FILE_BYTES) {
                    addIssue(issues, metadata.getId(), "MANIFEST_FILE_SIZE_INVALID");
                    continue;
                }

                JsonObject document;
                try (Reader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
                    JsonElement parsed = JsonParser.parseReader(reader);
                    if (parsed == null || !parsed.isJsonObject()) {
                        addIssue(issues, metadata.getId(), "MANIFEST_ROOT_NOT_OBJECT");
                        continue;
                    }
                    document = parsed.getAsJsonObject();
                }

                requireOnlyFields(document, TOP_LEVEL_FIELDS);
                if (requiredInteger(document, "schemaVersion") != SCHEMA_VERSION) {
                    addIssue(issues, metadata.getId(), "UNSUPPORTED_SCHEMA_VERSION");
                    continue;
                }

                String declaredModId = requiredString(document, "modId", 64);
                if (!metadata.getId().equals(declaredModId)) {
                    addIssue(issues, metadata.getId(), "MOD_ID_MISMATCH");
                    continue;
                }

                String declaredModVersion = requiredString(document, "modVersion", 64);
                String installedModVersion = metadata.getVersion().getFriendlyString();
                if (!installedModVersion.equals(declaredModVersion)) {
                    addIssue(issues, metadata.getId(), "MOD_VERSION_MISMATCH");
                    continue;
                }

                List<String> supportedVersions = requiredStringArray(
                        document, "minecraftVersions", 1, 16, 32, null);
                if (supportedVersions.stream().anyMatch(version ->
                        !version.equals("*") && !VERSION_PATTERN.matcher(version).matches())) {
                    addIssue(issues, metadata.getId(), "INVALID_MINECRAFT_VERSION_RANGE");
                    continue;
                }
                String currentVersion = server.getServerVersion();
                if (!supportedVersions.contains("*") && !supportedVersions.contains(currentVersion)) {
                    addIssue(issues, metadata.getId(), "MINECRAFT_VERSION_NOT_SUPPORTED");
                    continue;
                }

                JsonArray commands = requiredArray(document, "commands");
                if (commands.size() > MAX_COMMANDS_PER_MOD) {
                    addIssue(issues, metadata.getId(), "TOO_MANY_COMMANDS_IN_MANIFEST");
                    continue;
                }

                for (JsonElement element : commands) {
                    try {
                        JsonObject command = normalizeCommand(element, metadata, supportedVersions, liveRoots);
                        if (command == null) {
                            addIssue(issues, metadata.getId(), "COMMAND_ROOT_NOT_REGISTERED");
                            continue;
                        }
                        String root = command.get("root").getAsString();
                        if (conflictingRoots.contains(root) || manifests.containsKey(root)) {
                            manifests.remove(root);
                            conflictingRoots.add(root);
                            addIssue(issues, metadata.getId(), "DUPLICATE_COMMAND_ROOT_MANIFEST");
                            continue;
                        }
                        if (manifests.size() >= MAX_TOTAL_COMMANDS) {
                            addIssue(issues, metadata.getId(), "TOTAL_MANIFEST_COMMAND_LIMIT_REACHED");
                            break;
                        }
                        manifests.put(root, command);
                    } catch (IllegalArgumentException exception) {
                        addIssue(issues, metadata.getId(), exception.getMessage());
                    }
                }
            } catch (IOException | JsonParseException exception) {
                addIssue(issues, metadata.getId(), "MANIFEST_READ_OR_PARSE_FAILED");
            } catch (IllegalArgumentException exception) {
                addIssue(issues, metadata.getId(), exception.getMessage());
            } catch (RuntimeException exception) {
                addIssue(issues, metadata.getId(), "MANIFEST_REJECTED");
            }
        }

        if (loadedMods.size() > MAX_MODS) {
            addIssue(issues, "fabric-loader", "MOD_SCAN_LIMIT_REACHED");
        }
        return new Registry(Map.copyOf(manifests), issues, mods.size(), manifestFiles, manifests.size());
    }

    private static JsonObject normalizeCommand(
            JsonElement element,
            ModMetadata metadata,
            List<String> supportedVersions,
            Set<String> liveRoots) {
        if (element == null || !element.isJsonObject()) {
            throw new IllegalArgumentException("COMMAND_ENTRY_NOT_OBJECT");
        }
        JsonObject command = element.getAsJsonObject();
        requireOnlyFields(command, COMMAND_FIELDS);

        String root = requiredString(command, "root", 64);
        if (!ROOT_PATTERN.matcher(root).matches()) {
            throw new IllegalArgumentException("COMMAND_ROOT_INVALID");
        }
        if (!liveRoots.contains(root)) {
            return null;
        }

        Map<String, String> descriptions = requiredStringMap(
                command, "descriptions", 8, 256, LOCALE_PATTERN);
        List<String> keywords = requiredStringArray(command, "keywords", 1, MAX_KEYWORDS, 64, null);
        List<String> examples = optionalStringArray(command, "examples", MAX_EXAMPLES, 256);
        Map<String, String> argumentDescriptions = optionalStringMap(
                command, "argumentDescriptions", MAX_ARGUMENTS, 160, null);
        List<String> effects = requiredStringArray(command, "effects", 1, 8, 32, EFFECTS);

        String executionContext = requiredEnum(command, "executionContext", EXECUTION_CONTEXTS);
        String advisoryRisk = requiredEnum(command, "advisoryRisk", RISKS);
        String advisoryReversibility = requiredEnum(command, "advisoryReversibility", REVERSIBILITY);

        JsonObject normalized = new JsonObject();
        normalized.addProperty("root", root);
        normalized.addProperty("source_mod_id", metadata.getId());
        normalized.addProperty("source_mod_name", metadata.getName());
        normalized.addProperty("source_mod_version", metadata.getVersion().getFriendlyString());
        normalized.add("supported_minecraft_versions", toJsonArray(supportedVersions));
        normalized.add("descriptions", toJsonObject(descriptions));
        normalized.add("keywords", toJsonArray(keywords));
        normalized.add("examples", toJsonArray(examples));
        normalized.add("argument_descriptions", toJsonObject(argumentDescriptions));
        normalized.add("effects", toJsonArray(effects));
        normalized.addProperty("execution_context", executionContext);
        normalized.addProperty("advisory_risk", advisoryRisk);
        normalized.addProperty("advisory_reversibility", advisoryReversibility);
        normalized.addProperty("root_present_in_live_dispatcher", true);
        normalized.addProperty("ownership_verified", false);
        normalized.addProperty("binding", "exact_live_root_name_match_only");
        normalized.addProperty("trust", "untrusted_mod_supplied_metadata");
        return normalized;
    }

    private static void requireOnlyFields(JsonObject object, Set<String> allowed) {
        for (String key : object.keySet()) {
            if (!allowed.contains(key)) {
                throw new IllegalArgumentException("UNKNOWN_MANIFEST_FIELD");
            }
        }
    }

    private static JsonArray requiredArray(JsonObject object, String key) {
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonArray()) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        return value.getAsJsonArray();
    }

    private static String requiredString(JsonObject object, String key, int maxLength) {
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isString()) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        String text = value.getAsString();
        if (text.isBlank() || text.length() > maxLength || text.indexOf('\0') >= 0) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        return text;
    }

    private static int requiredInteger(JsonObject object, String key) {
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isNumber()) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        double number = value.getAsDouble();
        int integer = value.getAsInt();
        if (!Double.isFinite(number) || number != integer) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        return integer;
    }

    private static String requiredEnum(JsonObject object, String key, Set<String> allowed) {
        String value = requiredString(object, key, 48);
        if (!allowed.contains(value)) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        return value;
    }

    private static List<String> requiredStringArray(
            JsonObject object,
            String key,
            int minItems,
            int maxItems,
            int maxLength,
            Set<String> allowedValues) {
        JsonArray array = requiredArray(object, key);
        if (array.size() < minItems || array.size() > maxItems) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        List<String> values = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (JsonElement element : array) {
            if (element == null || !element.isJsonPrimitive() || !element.getAsJsonPrimitive().isString()) {
                throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
            }
            String value = element.getAsString();
            if (value.isBlank() || value.length() > maxLength || value.indexOf('\0') >= 0
                    || !seen.add(value) || (allowedValues != null && !allowedValues.contains(value))) {
                throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
            }
            values.add(value);
        }
        return List.copyOf(values);
    }

    private static List<String> optionalStringArray(
            JsonObject object, String key, int maxItems, int maxLength) {
        if (!object.has(key)) {
            return List.of();
        }
        return requiredStringArray(object, key, 0, maxItems, maxLength, null);
    }

    private static Map<String, String> requiredStringMap(
            JsonObject object,
            String key,
            int maxEntries,
            int maxValueLength,
            Pattern keyPattern) {
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonObject()) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        JsonObject source = value.getAsJsonObject();
        if (source.size() < 1 || source.size() > maxEntries) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        Map<String, String> result = new LinkedHashMap<>();
        for (Map.Entry<String, JsonElement> entry : source.entrySet()) {
            String mapKey = entry.getKey();
            JsonElement mapValue = entry.getValue();
            if (mapKey.isBlank() || mapKey.length() > 96 || (keyPattern != null && !keyPattern.matcher(mapKey).matches())
                    || mapValue == null || !mapValue.isJsonPrimitive()
                    || !mapValue.getAsJsonPrimitive().isString()) {
                throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
            }
            String text = mapValue.getAsString();
            if (text.isBlank() || text.length() > maxValueLength || text.indexOf('\0') >= 0) {
                throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
            }
            result.put(mapKey, text);
        }
        return Map.copyOf(result);
    }

    private static Map<String, String> optionalStringMap(
            JsonObject object,
            String key,
            int maxEntries,
            int maxValueLength,
            Pattern keyPattern) {
        if (!object.has(key)) {
            return Map.of();
        }
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonObject() || value.getAsJsonObject().size() > maxEntries) {
            throw new IllegalArgumentException("INVALID_" + key.toUpperCase());
        }
        if (value.getAsJsonObject().size() == 0) {
            return Map.of();
        }
        return requiredStringMap(object, key, maxEntries, maxValueLength, keyPattern);
    }

    private static JsonArray toJsonArray(List<String> values) {
        JsonArray array = new JsonArray();
        values.forEach(array::add);
        return array;
    }

    private static JsonObject toJsonObject(Map<String, String> values) {
        JsonObject object = new JsonObject();
        values.forEach(object::addProperty);
        return object;
    }

    private static void addIssue(JsonArray issues, String modId, String code) {
        if (issues.size() >= MAX_ISSUES) {
            return;
        }
        JsonObject issue = new JsonObject();
        issue.addProperty("mod_id", modId);
        issue.addProperty("code", code == null ? "MANIFEST_REJECTED" : code);
        issues.add(issue);
    }
}
