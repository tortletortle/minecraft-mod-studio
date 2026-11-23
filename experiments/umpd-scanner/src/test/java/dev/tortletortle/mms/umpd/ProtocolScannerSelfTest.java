package dev.tortletortle.mms.umpd;

import java.io.ByteArrayOutputStream;
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
        scannerDoesNotFollowSymlinkDirectories();
        scannerFindsProtocolReferencesInsideNestedJars();
        scannerRejectsLookalikeTypeNamesAndStringConstants();
        scannerRejectsMalformedConstantPoolReferences();
        scannerMapsIntermediaryClassNamesFromTinyV2();
        reportOutputCannotEscapeModsRootThroughSymlinks();
        System.out.println("UMPD self-tests passed: 10/10 (OS-dependent symlink assertions may be skipped when symlink creation is unavailable)");
    }

    private static void jsonParserHandlesNestedMetadata() {
        Object parsed = MiniJson.parse("{\"id\":\"demo\",\"depends\":{\"fabric\":\">=0.1\"},\"flags\":[true,3,null]}");
        check(parsed instanceof Map<?, ?>, "JSON root must be an object");
        Map<?, ?> root = (Map<?, ?>) parsed;
        check("demo".equals(root.get("id")), "JSON string field mismatch");
        check(root.get("depends") instanceof Map<?, ?>, "Nested JSON object missing");
        String serialized = MiniJson.stringify(parsed);
        check(MiniJson.parse(serialized) instanceof Map<?, ?>, "JSON writer output must parse");
        String deeplyNested = "[".repeat(129) + "0" + "]".repeat(129);
        boolean depthRejected = false;
        try { MiniJson.parse(deeplyNested); }
        catch (IllegalArgumentException expected) { depthRejected = true; }
        check(depthRejected, "JSON parser must reject nesting deeper than its configured safety bound");
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
        check(protocols.contains("DFU_CODEC"), "Codec class reference was not found");
        check(protocols.contains("STREAM_CODEC"), "StreamCodec class reference was not found");
        check(protocols.contains("NBT_PERSISTENCE"), "NBT class reference was not found");
        check(!protocols.contains("CONFIG_FRAMEWORK"), "Incidental string constant must not create a protocol hit");
        List<?> evidence = (List<?>) artifact.get("protocolEvidence");
        boolean codecMethodRef = evidence.stream().filter(Map.class::isInstance).map(Map.class::cast)
                .filter(item -> "DFU_CODEC".equals(item.get("protocol")))
                .anyMatch(item -> item.get("signals").toString().contains("member:com/mojang/serialization/Codec#fieldOf"));
        check(codecMethodRef, "Codec method reference was not captured");
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

    private static void scannerDoesNotFollowSymlinkDirectories() throws Exception {
        Path root = Files.createTempDirectory("umpd-symlink-root");
        Path external = Files.createTempDirectory("umpd-symlink-target");
        try (JarOutputStream jar = new JarOutputStream(Files.newOutputStream(external.resolve("outside.jar")))) {
            put(jar, "fabric.mod.json", "{\"schemaVersion\":1,\"id\":\"outside\"}".getBytes());
        }
        try {
            Files.createSymbolicLink(root.resolve("linked-outside"), external);
        } catch (UnsupportedOperationException | java.io.IOException | SecurityException unavailable) {
            System.out.println("Symlink traversal assertion skipped: " + unavailable.getClass().getSimpleName());
            return;
        }
        Map<String, Object> report = new ProtocolScanner().scanDirectory(root);
        Map<?, ?> summary = (Map<?, ?>) report.get("summary");
        check(((Number) summary.get("jarsDiscovered")).intValue() == 0,
                "Scanner must not traverse a symlinked directory outside the selected mods root");
    }

    private static void reportOutputCannotEscapeModsRootThroughSymlinks() throws Exception {
        Path root = Files.createTempDirectory("umpd-output-root");
        Path outside = Files.createTempDirectory("umpd-output-outside");
        boolean directRejected = false;
        try { ProtocolScanner.requireOutputOutsideInput(root, root.resolve("future/report.json")); }
        catch (IllegalArgumentException expected) { directRejected = true; }
        check(directRejected, "Report path under the mods root must be rejected even when parent directories do not exist");

        Path alias = outside.resolve("mods-alias");
        try {
            Files.createSymbolicLink(alias, root);
        } catch (UnsupportedOperationException | java.io.IOException | SecurityException unavailable) {
            System.out.println("Output symlink assertion skipped: " + unavailable.getClass().getSimpleName());
            return;
        }
        boolean aliasRejected = false;
        try { ProtocolScanner.requireOutputOutsideInput(root, alias.resolve("report.json")); }
        catch (IllegalArgumentException expected) { aliasRejected = true; }
        check(aliasRejected, "Report path through a parent symlink into the mods root must be rejected");

        Path externalReport = outside.resolve("safe-report.json");
        check(ProtocolScanner.requireOutputOutsideInput(root, externalReport).equals(externalReport.toAbsolutePath().normalize()),
                "A report path outside the mods root should remain valid");
    }

    private static void scannerEmitsVersionedReportContract() throws Exception {
        Path emptyMods = Files.createTempDirectory("umpd-empty-report-test");
        Map<String, Object> report = new ProtocolScanner().scanDirectory(emptyMods);
        check(((Number) report.get("reportVersion")).intValue() == 1, "Report schema version mismatch");
        check("UMPD-0.1.0".equals(report.get("scanner")), "Scanner identity missing from report");
        check("STATIC_NO_CLASS_LOADING_NO_EXTRACTION".equals(report.get("scanMode")), "Static scan mode missing");
        check(report.get("createdAt") instanceof String, "Report timestamp missing");
        Map<?, ?> mapping = (Map<?, ?>) report.get("classMapping");
        check(Boolean.FALSE.equals(mapping.get("applied")), "Empty mapping should be marked as not applied");
        Map<?, ?> summary = (Map<?, ?>) report.get("summary");
        check(((Number) summary.get("jarsDiscovered")).intValue() == 0, "Empty directory should discover zero JARs");
        check(((List<?>) report.get("artifacts")).isEmpty(), "Empty directory should produce no artifact records");
        Object reparsed = MiniJson.parse(MiniJson.stringify(report));
        check(reparsed instanceof Map<?, ?>, "Versioned report JSON round trip failed");
    }

    private static void scannerMapsIntermediaryClassNamesFromTinyV2() throws Exception {
        String tiny = """
                tiny\t2\t0\tofficial\tintermediary\tnamed
                c\ta/net/Nbt\tnet/minecraft/class_1234\tnet/minecraft/nbt/CompoundTag
                """;
        Path directory = Files.createTempDirectory("umpd-tiny-mapping-test");
        Path mappingPath = directory.resolve("mappings.tiny");
        Files.writeString(mappingPath, tiny);
        TinyV2Mappings.Mapping mapping = TinyV2Mappings.load(mappingPath, "intermediary", "named");
        check(mapping.classNames().get("net/minecraft/class_1234").equals("net/minecraft/nbt/CompoundTag"),
                "Tiny v2 namespace columns were not selected correctly");
        check(mapping.sha256().length() == 64, "Mapping file SHA-256 was not calculated");
        check(mapping.sourcePath().equals(mappingPath.toAbsolutePath().normalize().toString()),
                "Mapping file source path was not retained");

        byte[] fixtureClass;
        try (InputStream in = ProtocolScannerSelfTest.class.getResourceAsStream("/dev/tortletortle/mms/umpd/ProtocolScannerSelfTest$MappedFixture.class")) {
            if (in == null) throw new AssertionError("Mapped fixture class is missing");
            fixtureClass = in.readAllBytes();
        }
        Path jarPath = directory.resolve("mapped-mod.jar");
        try (JarOutputStream jar = new JarOutputStream(Files.newOutputStream(jarPath))) {
            put(jar, "fabric.mod.json", "{\"schemaVersion\":1,\"id\":\"mapped_mod\"}".getBytes());
            put(jar, "dev/example/MappedFixture.class", fixtureClass);
        }

        Map<String, Object> withoutMapping = new ProtocolScanner().scanDirectory(directory);
        Map<?, ?> plainArtifact = (Map<?, ?>) ((List<?>) withoutMapping.get("artifacts")).get(0);
        check(!((List<?>) plainArtifact.get("protocols")).contains("NBT_PERSISTENCE"),
                "Intermediary class name must not be mistaken for a named API class");

        Map<String, Object> mappedReport = new ProtocolScanner(mapping).scanDirectory(directory);
        Map<?, ?> artifact = (Map<?, ?>) ((List<?>) mappedReport.get("artifacts")).get(0);
        check(((List<?>) artifact.get("protocols")).contains("NBT_PERSISTENCE"),
                "Tiny v2 class mapping did not expose the mapped NBT type");
        Map<?, ?> mappingSummary = (Map<?, ?>) mappedReport.get("classMapping");
        check(Boolean.TRUE.equals(mappingSummary.get("applied")), "Mapping provenance was not recorded");
        check(((Number) mappingSummary.get("classMappingCount")).intValue() == 1,
                "Mapping class count was not recorded");
    }

    private static void scannerRejectsMalformedConstantPoolReferences() throws Exception {
        byte[] malformed = new byte[] {
                (byte) 0xCA, (byte) 0xFE, (byte) 0xBA, (byte) 0xBE,
                0, 0, 0, 52, 0, 2,
                10, 0, 1, 0, 1
        };
        boolean rejected = false;
        try { new ClassFileSignatureScanner().scan(malformed); }
        catch (java.io.IOException expected) { rejected = true; }
        check(rejected, "Malformed constant-pool references must be rejected as an IOException");
    }

    private static void scannerRejectsLookalikeTypeNamesAndStringConstants() throws Exception {
        byte[] fixtureClass;
        byte[] lookalikeClass;
        try (InputStream in = ProtocolScannerSelfTest.class.getResourceAsStream("/dev/tortletortle/mms/umpd/ProtocolScannerSelfTest$FalsePositiveFixture.class")) {
            if (in == null) throw new AssertionError("False-positive fixture class is missing");
            fixtureClass = in.readAllBytes();
        }
        try (InputStream in = ProtocolScannerSelfTest.class.getResourceAsStream("/com/example/FakeStreamCodecHelper.class")) {
            if (in == null) throw new AssertionError("Lookalike helper class is missing");
            lookalikeClass = in.readAllBytes();
        }

        Path directory = Files.createTempDirectory("umpd-false-positive-test");
        Path jarPath = directory.resolve("lookalike.jar");
        try (JarOutputStream jar = new JarOutputStream(Files.newOutputStream(jarPath))) {
            put(jar, "dev/example/FalsePositiveFixture.class", fixtureClass);
            put(jar, "com/example/FakeStreamCodecHelper.class", lookalikeClass);
        }
        Map<String, Object> report = new ProtocolScanner().scanDirectory(directory);
        Map<?, ?> artifact = (Map<?, ?>) ((List<?>) report.get("artifacts")).get(0);
        check(((List<?>) artifact.get("protocols")).isEmpty(),
                "A lookalike class name or protocol text constant must not create a protocol hit");
    }

    private static void scannerFindsProtocolReferencesInsideNestedJars() throws Exception {
        byte[] fixtureClass;
        try (InputStream in = ProtocolScannerSelfTest.class.getResourceAsStream("/dev/tortletortle/mms/umpd/ProtocolScannerSelfTest$ProtocolFixture.class")) {
            if (in == null) throw new AssertionError("Compiled nested fixture class is missing");
            fixtureClass = in.readAllBytes();
        }

        ByteArrayOutputStream deeperBytes = new ByteArrayOutputStream();
        try (JarOutputStream deeper = new JarOutputStream(deeperBytes)) {
            put(deeper, "dev/example/DeepNestedProtocolFixture.class", fixtureClass);
        }
        ByteArrayOutputStream nestedBytes = new ByteArrayOutputStream();
        try (JarOutputStream nested = new JarOutputStream(nestedBytes)) {
            put(nested, "dev/example/NestedProtocolFixture.class", fixtureClass);
            put(nested, "META-INF/jars/deeper-lib.jar", deeperBytes.toByteArray());
        }

        Path directory = Files.createTempDirectory("umpd-nested-jar-test");
        Path outerPath = directory.resolve("outer-mod.jar");
        try (JarOutputStream outer = new JarOutputStream(Files.newOutputStream(outerPath))) {
            put(outer, "fabric.mod.json", "{\"schemaVersion\":1,\"id\":\"outer_mod\"}".getBytes());
            put(outer, "META-INF/jars/nested-lib.jar", nestedBytes.toByteArray());
        }

        Map<String, Object> report = new ProtocolScanner().scanDirectory(directory);
        Map<?, ?> artifact = (Map<?, ?>) ((List<?>) report.get("artifacts")).get(0);
        check(((Number) artifact.get("nestedJarArchivesDiscovered")).intValue() == 2,
                "Recursive nested JAR discovery count mismatch");
        check(((Number) artifact.get("nestedJarArchivesScanned")).intValue() == 2,
                "Recursive nested JAR scan count mismatch");
        check(((Number) artifact.get("nestedJarClassesScanned")).intValue() == 2,
                "Nested and deeper nested JAR class scan count mismatch");
        List<?> protocols = (List<?>) artifact.get("protocols");
        check(protocols.contains("DFU_CODEC"), "Nested Codec class reference was not detected");
        check(protocols.contains("STREAM_CODEC"), "Nested StreamCodec class reference was not detected");
        check(protocols.contains("NBT_PERSISTENCE"), "Nested NBT class reference was not detected");
        List<?> evidence = (List<?>) artifact.get("protocolEvidence");
        boolean nestedEvidence = evidence.stream().filter(Map.class::isInstance).map(Map.class::cast)
                .anyMatch(item -> item.get("classPath").toString().contains("META-INF/jars/nested-lib.jar!/"));
        boolean deepEvidence = evidence.stream().filter(Map.class::isInstance).map(Map.class::cast)
                .anyMatch(item -> item.get("classPath").toString().contains("META-INF/jars/nested-lib.jar!/META-INF/jars/deeper-lib.jar!/"));
        check(nestedEvidence, "Nested JAR evidence path must retain its container provenance");
        check(deepEvidence, "Recursive nested JAR evidence path must retain both container levels");
    }

    private static void put(JarOutputStream jar, String name, byte[] bytes) throws Exception {
        jar.putNextEntry(new JarEntry(name));
        jar.write(bytes);
        jar.closeEntry();
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    /** Lookalike names and text constants must not count as API references. */
    static final class FalsePositiveFixture {
        static com.example.FakeStreamCodecHelper helper;
        static final String CODEC_TEXT = "com/mojang/serialization/Codec";
        static final String CONFIG_TEXT = "ModConfigSpec";
    }

    /** Intermediary class name is normalized only when a matching Tiny v2 map is supplied. */
    static final class MappedFixture {
        static net.minecraft.class_1234 tag;
    }

    /** Fixture declares protocol types and member references; the scanner never executes it. */
    static final class ProtocolFixture {
        static com.mojang.serialization.Codec<?> codec;
        static net.minecraft.network.codec.StreamCodec<Object, Object> stream;
        static net.minecraft.nbt.CompoundTag tag;
        static final String INCIDENTAL_TEXT = "ModConfigSpec";
        static void exercise(Object buffer) {
            codec.fieldOf("name");
            stream.encode(buffer, new Object());
            stream.decode(buffer);
            tag.getInt("value");
        }
    }
}
