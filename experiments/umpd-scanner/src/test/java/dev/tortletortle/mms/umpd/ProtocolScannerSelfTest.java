package dev.tortletortle.mms.umpd;

import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;

/** Dependency-free acceptance tests, invoked by the Gradle verifyScanner task. */
public final class ProtocolScannerSelfTest {
    private ProtocolScannerSelfTest() {}

    public static void main(String[] args) throws Exception {
        jsonParserHandlesNestedMetadata();
        scannerFindsLoaderMetadataResourcesAndBytecodeSignals();
        scannerExtractsNeoForgeModIdsWithoutMistakingDependencyIds();
        scannerRejectsNonDirectoryInput();
        System.out.println("UMPD self-tests passed: 4/4");
    }

    private static void jsonParserHandlesNestedMetadata() {
        Object parsed = MiniJson.parse("{\"id\":\"demo\",\"depends\":{\"fabric\":\">=0.1\"},\"flags\":[true,3,null]}");
        check(parsed instanceof Map<?, ?>, "JSON root must be an object");
        Map<?, ?> root = (Map<?, ?>) parsed;
        check("demo".equals(root.get("id")), "JSON string field mismatch");
        check(root.get("depends") instanceof Map<?, ?>, "Nested JSON object missing");
        String serialized = MiniJson.stringify(parsed);
        check(MiniJson.parse(serialized) instanceof Map<?, ?>, "JSON writer output must parse");
    }

    private static void scannerFindsLoaderMetadataResourcesAndBytecodeSignals() throws Exception {
        Path directory = Files.createTempDirectory("umpd-self-test");
        Path jarPath = directory.resolve("demo-mod.jar");
        byte[] fixtureClass;
        try (InputStream in = ProtocolScannerSelfTest.class.getResourceAsStream("/dev/tortletortle/mms/umpd/ProtocolScannerSelfTest$ProtocolFixture.class")) {
            if (in == null) throw new AssertionError("Compiled fixture class is missing");
            fixtureClass = in.readAllBytes();
        }
        try (JarOutputStream jar = new JarOutputStream(Files.newOutputStream(jarPath))) {
            put(jar, "fabric.mod.json", "{\"schemaVersion\":1,\"id\":\"demo_mod\",\"version\":\"1.2.3\",\"name\":\"Demo Mod\",\"depends\":{\"fabricloader\":\">=0.16\"}}".getBytes());
            put(jar, "config/demo.toml", "enabled=true".getBytes());
            put(jar, "assets/demo/lang/en_us.json", "{\"item.demo\":\"Demo\"}".getBytes());
            put(jar, "data/demo/recipes/demo.json", "{}".getBytes());
            put(jar, "dev/example/ProtocolFixture.class", fixtureClass);
        }

        Map<String, Object> report = new ProtocolScanner().scanDirectory(directory);
        Map<?, ?> summary = (Map<?, ?>) report.get("summary");
        check(((Number) summary.get("jarsScanned")).intValue() == 1, "Expected one scanned JAR");
        List<?> artifacts = (List<?>) report.get("artifacts");
        Map<?, ?> artifact = (Map<?, ?>) artifacts.get(0);
        check("FABRIC".equals(artifact.get("loader")), "Fabric metadata was not detected");
        check(((List<?>) artifact.get("modIds")).contains("demo_mod"), "Mod ID was not extracted");
        check(((Map<?, ?>) artifact.get("fileFormatCounts")).containsKey("TOML"), "TOML resource was not counted");
        check(((Map<?, ?>) artifact.get("entryCounts")).containsKey("assets"), "Assets directory was not counted");
        check(((Map<?, ?>) artifact.get("entryCounts")).containsKey("data"), "Data directory was not counted");
        check(((Map<?, ?>) artifact.get("resourcePathCounts")).containsKey("assets/lang"), "Asset path category missing");
        check(((Map<?, ?>) artifact.get("resourcePathCounts")).containsKey("data/recipes"), "Datapack path category missing");
        check(((List<?>) artifact.get("configPathSamples")).contains("config/demo.toml"), "Config path sample missing");
        List<?> protocols = (List<?>) artifact.get("protocols");
        check(protocols.contains("DFU_CODEC"), "Codec constant-pool signature was not found");
        check(protocols.contains("STREAM_CODEC"), "StreamCodec constant-pool signature was not found");
        check(protocols.contains("NBT_PERSISTENCE"), "NBT constant-pool signature was not found");
        check("STATIC_NO_CLASS_LOADING_NO_EXTRACTION".equals(report.get("scanMode")), "Safety mode missing");
    }

    private static void scannerExtractsNeoForgeModIdsWithoutMistakingDependencyIds() throws Exception {
        Path directory = Files.createTempDirectory("umpd-neoforge-test");
        Path jarPath = directory.resolve("neo-mod.jar");
        String toml = """
                modLoader = "javafml"
                loaderVersion = "[1,)"

                [[mods]]
                modId = "neo_demo"
                version = "2.0.0"
                displayName = "Neo Demo"

                [[dependencies.neo_demo]]
                modId = "minecraft"
                mandatory = true
                """;
        try (JarOutputStream jar = new JarOutputStream(Files.newOutputStream(jarPath))) {
            put(jar, "META-INF/neoforge.mods.toml", toml.getBytes());
        }
        Map<String, Object> report = new ProtocolScanner().scanDirectory(directory);
        Map<?, ?> artifact = (Map<?, ?>) ((List<?>) report.get("artifacts")).get(0);
        check("NEOFORGE".equals(artifact.get("loader")), "NeoForge metadata was not detected");
        List<?> ids = (List<?>) artifact.get("modIds");
        check(ids.equals(List.of("neo_demo")), "Dependency modId leaked into primary mod IDs: " + ids);
    }

    private static void scannerRejectsNonDirectoryInput() throws Exception {
        Path file = Files.createTempFile("umpd-not-directory", ".txt");
        boolean rejected = false;
        try { new ProtocolScanner().scanDirectory(file); }
        catch (java.io.IOException expected) { rejected = true; }
        check(rejected, "Scanner must reject a non-directory input");
    }

    private static void put(JarOutputStream jar, String name, byte[] bytes) throws Exception {
        jar.putNextEntry(new JarEntry(name));
        jar.write(bytes);
        jar.closeEntry();
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    /** Strings become UTF8 constant-pool entries; no fixture code is executed by the scanner. */
    static final class ProtocolFixture {
        static final String CODEC = "com/mojang/serialization/Codec";
        static final String STREAM = "net/minecraft/network/codec/StreamCodec";
        static final String NBT = "net/minecraft/nbt/CompoundTag";
    }
}
