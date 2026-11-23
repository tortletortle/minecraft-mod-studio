package dev.tortletortle.mms.umpd;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

/** Static, non-executing scanner for Minecraft Java mod JARs. */
public final class ProtocolScanner {
    static final int MAX_JARS = 1_000;
    static final long MAX_JAR_BYTES = 512L * 1024 * 1024;
    static final long MAX_TOTAL_INPUT_BYTES = 8L * 1024 * 1024 * 1024;
    static final int MAX_ENTRIES_PER_JAR = 100_000;
    static final int MAX_CLASS_BYTES = 8 * 1024 * 1024;
    static final long MAX_TOTAL_CLASS_BYTES_PER_JAR = 128L * 1024 * 1024;
    static final int MAX_METADATA_BYTES = 2 * 1024 * 1024;
    static final int MAX_EVIDENCE_PER_JAR = 1_000;
    static final int MAX_WARNINGS_PER_JAR = 1_000;
    static final int MAX_NESTED_ARCHIVES = 100;
    static final int MAX_NESTED_DEPTH = 2;
    static final int MAX_NESTED_ENTRIES = 100_000;
    static final int MAX_NESTED_ARCHIVE_BYTES = 64 * 1024 * 1024;
    static final int MAX_NESTED_ENTRY_BYTES = 64 * 1024 * 1024;
    static final long MAX_TOTAL_NESTED_ARCHIVE_BYTES = 256L * 1024 * 1024;
    static final long MAX_TOTAL_NESTED_UNCOMPRESSED_BYTES = 512L * 1024 * 1024;
    private final TinyV2Mappings.Mapping mappings;
    private final ClassFileSignatureScanner classScanner;

    public ProtocolScanner() {
        this(TinyV2Mappings.Mapping.none());
    }

    ProtocolScanner(TinyV2Mappings.Mapping mappings) {
        this.mappings = mappings;
        this.classScanner = new ClassFileSignatureScanner(mappings);
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2 || !"scan".equals(args[0])) {
            System.err.println("Usage: umpd scan <mods-directory> [--out <report.json>] [--mappings <tiny-v2-file> [--from-namespace intermediary] [--to-namespace named]]");
            System.exit(2);
        }
        Path input = Path.of(args[1]).toAbsolutePath().normalize();
        Path output = null;
        Path mappingPath = null;
        String fromNamespace = "intermediary";
        String toNamespace = "named";
        for (int i = 2; i < args.length; i++) {
            if ("--out".equals(args[i]) && i + 1 < args.length) output = Path.of(args[++i]).toAbsolutePath().normalize();
            else if ("--mappings".equals(args[i]) && i + 1 < args.length) mappingPath = Path.of(args[++i]).toAbsolutePath().normalize();
            else if ("--from-namespace".equals(args[i]) && i + 1 < args.length) fromNamespace = args[++i];
            else if ("--to-namespace".equals(args[i]) && i + 1 < args.length) toNamespace = args[++i];
            else throw new IllegalArgumentException("Unknown or incomplete argument: " + args[i]);
        }
        if (output != null) output = requireOutputOutsideInput(input, output);
        if (mappingPath == null && (!"intermediary".equals(fromNamespace) || !"named".equals(toNamespace))) {
            throw new IllegalArgumentException("Namespace overrides require --mappings");
        }
        TinyV2Mappings.Mapping mapping = mappingPath == null
                ? TinyV2Mappings.Mapping.none()
                : TinyV2Mappings.load(mappingPath, fromNamespace, toNamespace);
        ProtocolScanner scanner = new ProtocolScanner(mapping);
        Map<String, Object> report = scanner.scanDirectory(input);
        String json = MiniJson.stringify(report) + System.lineSeparator();
        if (output == null) System.out.print(json);
        else {
            Path parent = output.getParent();
            if (parent != null) Files.createDirectories(parent);
            Files.writeString(output, json, StandardCharsets.UTF_8);
            System.out.println("UMPD report written: " + output);
            System.out.println("JARs scanned: " + ((Map<?, ?>) report.get("summary")).get("jarsScanned"));
        }
    }

    static Path requireOutputOutsideInput(Path input, Path output) throws IOException {
        Path realInput = input.toRealPath();
        Path normalized = output.toAbsolutePath().normalize();
        Path fileName = normalized.getFileName();
        if (fileName == null) throw new IllegalArgumentException("Report output must name a file");
        Path parent = normalized.getParent();
        if (parent == null) parent = Path.of(".").toAbsolutePath().normalize();

        List<Path> missingParents = new ArrayList<>();
        Path existing = parent;
        while (existing != null && !Files.exists(existing, LinkOption.NOFOLLOW_LINKS)) {
            missingParents.add(0, existing.getFileName());
            existing = existing.getParent();
        }
        if (existing == null) throw new IOException("Cannot resolve report output parent: " + parent);
        Path resolvedParent = existing.toRealPath();
        for (Path component : missingParents) resolvedParent = resolvedParent.resolve(component);
        Path resolvedOutput = resolvedParent.resolve(fileName).normalize();
        if (resolvedOutput.startsWith(realInput)) {
            throw new IllegalArgumentException("Report output must be outside the scanned mods directory");
        }
        if (Files.isSymbolicLink(normalized)) {
            throw new IllegalArgumentException("Report output must not be a symbolic link");
        }
        if (Files.exists(normalized, LinkOption.NOFOLLOW_LINKS)
                && normalized.toRealPath().startsWith(realInput)) {
            throw new IllegalArgumentException("Report output must not resolve into the scanned mods directory");
        }
        return normalized;
    }

    public Map<String, Object> scanDirectory(Path directory) throws IOException {
        if (!Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS)) {
            throw new IOException("Input is not a directory: " + directory);
        }
        List<Path> jars;
        try (Stream<Path> walk = Files.walk(directory)) {
            jars = walk.filter(path -> Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
                    .filter(path -> path.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".jar"))
                    .limit(MAX_JARS + 1L)
                    .sorted(Comparator.comparing(path -> directory.relativize(path).toString())).toList();
        }
        if (jars.size() > MAX_JARS) throw new IOException("JAR limit exceeded: maximum " + MAX_JARS);
        long totalInputBytes = 0;
        for (Path jar : jars) {
            long size = Files.size(jar);
            if (size > MAX_JAR_BYTES) throw new IOException("JAR exceeds size limit: " + jar);
            totalInputBytes += size;
            if (totalInputBytes > MAX_TOTAL_INPUT_BYTES) throw new IOException("Total JAR input size exceeds 8 GiB budget");
        }

        List<Map<String, Object>> artifacts = new ArrayList<>();
        Map<String, Integer> protocolHits = new LinkedHashMap<>();
        int failed = 0;
        for (Path jar : jars) {
            try {
                Map<String, Object> artifact = scanJar(directory, jar);
                artifacts.add(artifact);
                @SuppressWarnings("unchecked") List<String> protocols = (List<String>) artifact.get("protocols");
                for (String protocol : protocols) protocolHits.merge(protocol, 1, Integer::sum);
            } catch (Exception e) {
                failed++;
                Map<String, Object> error = new LinkedHashMap<>();
                error.put("file", directory.relativize(jar).toString().replace('\\', '/'));
                error.put("status", "SCAN_FAILED");
                error.put("error", bounded(e.getClass().getSimpleName() + ": " + e.getMessage(), 512));
                artifacts.add(error);
            }
        }
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("jarsDiscovered", jars.size());
        summary.put("jarsScanned", jars.size() - failed);
        summary.put("jarsFailed", failed);
        summary.put("protocolHitCountsByJar", protocolHits);

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("reportVersion", 1);
        report.put("scanner", "UMPD-0.1.0");
        report.put("createdAt", Instant.now().toString());
        report.put("inputDirectory", directory.toString());
        report.put("scanMode", "STATIC_NO_CLASS_LOADING_NO_EXTRACTION");
        Map<String, Object> mappingSummary = new LinkedHashMap<>();
        mappingSummary.put("applied", !mappings.classNames().isEmpty());
        mappingSummary.put("fromNamespace", mappings.fromNamespace());
        mappingSummary.put("toNamespace", mappings.toNamespace());
        mappingSummary.put("classMappingCount", mappings.classNames().size());
        mappingSummary.put("sha256", mappings.sha256());
        mappingSummary.put("source", mappings.sourcePath());
        report.put("classMapping", mappingSummary);
        report.put("summary", summary);
        report.put("artifacts", artifacts);
        return report;
    }

    private Map<String, Object> scanJar(Path root, Path path) throws IOException, NoSuchAlgorithmException {
        Map<String, Object> artifact = new LinkedHashMap<>();
        artifact.put("file", root.relativize(path).toString().replace('\\', '/'));
        artifact.put("sizeBytes", Files.size(path));
        artifact.put("sha256", sha256(path));
        Map<String, Object> metadata = new LinkedHashMap<>();
        Map<String, Integer> entryCounts = new LinkedHashMap<>();
        Map<String, Integer> formatCounts = new LinkedHashMap<>();
        Map<String, Integer> resourcePathCounts = new LinkedHashMap<>();
        Map<String, Set<String>> resourceNamespaces = new LinkedHashMap<>();
        List<String> configPathSamples = new ArrayList<>();
        List<String> nestedJarSamples = new ArrayList<>();
        Map<String, Integer> protocolClassHits = new LinkedHashMap<>();
        List<Map<String, Object>> evidence = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        int[] warningOverflow = {0};
        NestedScanAccumulator nestedScan = new NestedScanAccumulator();
        Set<String> modIds = new LinkedHashSet<>();
        String loader = "UNKNOWN";
        int classesScanned = 0;
        int classEntriesSeen = 0;
        long classBytesScanned = 0;
        int entriesScanned = 0;
        int evidenceOverflow = 0;

        try (JarFile jar = new JarFile(path.toFile(), false)) {
            var entries = jar.entries();
            while (entries.hasMoreElements()) {
                JarEntry entry = entries.nextElement();
                if (entry.isDirectory()) continue;
                if (++entriesScanned > MAX_ENTRIES_PER_JAR) {
                    addWarning(warnings, warningOverflow, "entry_limit_exceeded");
                    break;
                }
                String name = entry.getName();
                entryCounts.merge(topLevel(name), 1, Integer::sum);
                detectPathSignals(name, formatCounts, resourcePathCounts, resourceNamespaces, configPathSamples);
                if (name.toLowerCase(Locale.ROOT).endsWith(".jar")) {
                    entryCounts.merge("<nested-jar>", 1, Integer::sum);
                    if (nestedJarSamples.size() < 100) nestedJarSamples.add(name);
                    scanNestedJarEntry(jar, entry, name, nestedScan);
                }

                if (name.equals("fabric.mod.json")) {
                    String text = readText(jar, entry, MAX_METADATA_BYTES);
                    Object parsed = MiniJson.parse(text);
                    if (parsed instanceof Map<?, ?> map) {
                        metadata.put("fabric", safeMetadata(map));
                        Object id = map.get("id");
                        if (id instanceof String value) modIds.add(value);
                        loader = "FABRIC";
                    } else addWarning(warnings, warningOverflow, "fabric_mod_json_root_not_object");
                } else if (name.equals("META-INF/neoforge.mods.toml") || name.equals("META-INF/mods.toml")) {
                    String text = readText(jar, entry, MAX_METADATA_BYTES);
                    Map<String, Object> toml = parseTomlMetadata(text);
                    metadata.put(name.endsWith("neoforge.mods.toml") ? "neoforge" : "forge", toml);
                    Object ids = toml.get("modIds");
                    if (ids instanceof List<?> list) for (Object id : list) if (id instanceof String s) modIds.add(s);
                    loader = name.endsWith("neoforge.mods.toml") ? "NEOFORGE" : "FORGE_OR_NEOFORGE";
                }

                if (name.endsWith(".class")) {
                    classEntriesSeen++;
                    if (entry.getSize() > MAX_CLASS_BYTES) {
                        addWarning(warnings, warningOverflow, "class_too_large:" + bounded(name, 180));
                        continue;
                    }
                    if (entry.getSize() > 0 && classBytesScanned + entry.getSize() > MAX_TOTAL_CLASS_BYTES_PER_JAR) {
                        addWarning(warnings, warningOverflow, "class_byte_budget_exceeded");
                        continue;
                    }
                    byte[] bytes = readBounded(jar.getInputStream(entry), MAX_CLASS_BYTES);
                    if (bytes.length > MAX_CLASS_BYTES) {
                        addWarning(warnings, warningOverflow, "class_too_large:" + bounded(name, 180));
                        continue;
                    }
                    if (classBytesScanned + bytes.length > MAX_TOTAL_CLASS_BYTES_PER_JAR) {
                        addWarning(warnings, warningOverflow, "class_byte_budget_exceeded");
                        continue;
                    }
                    classBytesScanned += bytes.length;
                    try {
                        Map<String, Set<String>> hits = classScanner.scan(bytes);
                        classesScanned++;
                        for (Map.Entry<String, Set<String>> hit : hits.entrySet()) {
                            protocolClassHits.merge(hit.getKey(), 1, Integer::sum);
                            if (evidence.size() < MAX_EVIDENCE_PER_JAR) {
                                Map<String, Object> item = new LinkedHashMap<>();
                                item.put("protocol", hit.getKey());
                                boolean hasCallSite = hit.getValue().stream().anyMatch(signal ->
                                        signal.startsWith("callsite:") || signal.startsWith("mapped-callsite:"));
                                item.put("evidenceLevel", hasCallSite ? "BYTECODE_CALL_SITE" : "CLASS_TYPE_OR_MEMBER_REFERENCE");
                                item.put("classPath", name);
                                item.put("signals", hit.getValue());
                                evidence.add(item);
                            } else evidenceOverflow++;
                        }
                    } catch (IOException | RuntimeException e) {
                        addWarning(warnings, warningOverflow, "class_parse_failed:" + bounded(name, 180));
                    }
                }
            }
        }
        for (Map.Entry<String, Integer> hit : nestedScan.protocolClassHits.entrySet()) {
            protocolClassHits.merge(hit.getKey(), hit.getValue(), Integer::sum);
        }
        for (Map<String, Object> nestedEvidence : nestedScan.evidence) {
            if (evidence.size() < MAX_EVIDENCE_PER_JAR) evidence.add(nestedEvidence);
            else evidenceOverflow++;
        }
        evidenceOverflow += nestedScan.evidenceOverflow;
        for (String nestedWarning : nestedScan.warnings) addWarning(warnings, warningOverflow, nestedWarning);
        warningOverflow[0] += nestedScan.warningsOverflow;
        artifact.put("status", "SCANNED");
        artifact.put("loader", loader);
        artifact.put("modIds", new ArrayList<>(modIds));
        artifact.put("metadata", metadata);
        artifact.put("entryCounts", entryCounts);
        artifact.put("fileFormatCounts", formatCounts);
        artifact.put("resourcePathCounts", resourcePathCounts);
        artifact.put("resourceNamespaces", resourceNamespaces);
        artifact.put("configPathSamples", configPathSamples);
        artifact.put("nestedJarEntryCount", entryCounts.getOrDefault("<nested-jar>", 0));
        artifact.put("nestedJarSamples", nestedJarSamples);
        artifact.put("nestedJarArchivesDiscovered", nestedScan.archivesDiscovered);
        artifact.put("nestedJarArchivesScanned", nestedScan.archivesScanned);
        artifact.put("nestedJarEntriesScanned", nestedScan.entriesScanned);
        artifact.put("nestedJarClassesScanned", nestedScan.classesScanned);
        artifact.put("nestedJarClassBytesScanned", nestedScan.classBytesScanned);
        artifact.put("nestedJarArchiveBytesScanned", nestedScan.nestedArchiveBytes);
        artifact.put("nestedJarUncompressedBytesScanned", nestedScan.uncompressedBytesScanned);
        artifact.put("nestedJarProtocolClassHitCounts", nestedScan.protocolClassHits);
        artifact.put("classEntriesSeen", classEntriesSeen);
        artifact.put("classesScanned", classesScanned);
        artifact.put("classBytesScanned", classBytesScanned);
        artifact.put("protocolClassHitCounts", protocolClassHits);
        artifact.put("protocols", new ArrayList<>(protocolClassHits.keySet()));
        artifact.put("protocolEvidence", evidence);
        artifact.put("evidenceOverflow", evidenceOverflow);
        artifact.put("warnings", warnings);
        artifact.put("warningOverflow", warningOverflow[0]);
        artifact.put("entriesScanned", entriesScanned);
        return artifact;
    }

    private void scanNestedJarEntry(JarFile jar, JarEntry entry, String entryName,
                                    NestedScanAccumulator stats) {
        stats.archivesDiscovered++;
        if (stats.archivesScanned >= MAX_NESTED_ARCHIVES) {
            stats.warn("nested_jar_archive_limit_exceeded:" + bounded(entryName, 180));
            return;
        }
        if (entry.getSize() > MAX_NESTED_ARCHIVE_BYTES) {
            stats.warn("nested_jar_too_large:" + bounded(entryName, 180));
            return;
        }
        try {
            byte[] nestedBytes = readBounded(jar.getInputStream(entry), MAX_NESTED_ARCHIVE_BYTES);
            if (nestedBytes.length > MAX_NESTED_ARCHIVE_BYTES) {
                stats.warn("nested_jar_too_large:" + bounded(entryName, 180));
                return;
            }
            if (stats.nestedArchiveBytes + nestedBytes.length > MAX_TOTAL_NESTED_ARCHIVE_BYTES
                    || stats.uncompressedBytesScanned + nestedBytes.length > MAX_TOTAL_NESTED_UNCOMPRESSED_BYTES) {
                stats.warn("nested_jar_archive_byte_budget_exceeded");
                return;
            }
            stats.nestedArchiveBytes += nestedBytes.length;
            stats.uncompressedBytesScanned += nestedBytes.length;
            scanNestedArchive(nestedBytes, entryName, 1, stats);
        } catch (IOException e) {
            stats.warn("nested_jar_read_failed:" + bounded(entryName, 180));
        }
    }

    private void scanNestedArchive(byte[] archiveBytes, String archivePath, int depth,
                                   NestedScanAccumulator stats) {
        if (depth > MAX_NESTED_DEPTH) {
            stats.warn("nested_jar_depth_limit:" + bounded(archivePath, 180));
            return;
        }
        if (stats.archivesScanned >= MAX_NESTED_ARCHIVES) {
            stats.warn("nested_jar_archive_limit_exceeded:" + bounded(archivePath, 180));
            return;
        }
        stats.archivesScanned++;
        boolean foundEntry = false;
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(archiveBytes))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) {
                    zip.closeEntry();
                    continue;
                }
                foundEntry = true;
                if (++stats.entriesScanned > MAX_NESTED_ENTRIES) {
                    stats.warn("nested_jar_entry_limit_exceeded");
                    return;
                }
                String name = entry.getName();
                String qualifiedName = archivePath + "!/" + name;
                String lower = name.toLowerCase(Locale.ROOT);

                if (lower.endsWith(".class")) {
                    if (entry.getSize() > MAX_CLASS_BYTES) {
                        drainNestedEntry(zip, MAX_NESTED_ENTRY_BYTES, stats);
                        stats.warn("nested_class_too_large:" + bounded(qualifiedName, 180));
                        continue;
                    }
                    byte[] classBytes = readNestedEntry(zip, MAX_CLASS_BYTES, stats);
                    stats.classBytesScanned += classBytes.length;
                    try {
                        Map<String, Set<String>> hits = classScanner.scan(classBytes);
                        stats.classesScanned++;
                        for (Map.Entry<String, Set<String>> hit : hits.entrySet()) {
                            stats.protocolClassHits.merge(hit.getKey(), 1, Integer::sum);
                            if (stats.evidence.size() < MAX_EVIDENCE_PER_JAR) {
                                Map<String, Object> item = new LinkedHashMap<>();
                                item.put("protocol", hit.getKey());
                                boolean hasCallSite = hit.getValue().stream().anyMatch(signal ->
                                        signal.startsWith("callsite:") || signal.startsWith("mapped-callsite:"));
                                item.put("evidenceLevel", hasCallSite ? "BYTECODE_CALL_SITE" : "CLASS_TYPE_OR_MEMBER_REFERENCE");
                                item.put("classPath", qualifiedName);
                                item.put("container", archivePath);
                                item.put("signals", hit.getValue());
                                stats.evidence.add(item);
                            } else stats.evidenceOverflow++;
                        }
                    } catch (IOException | RuntimeException e) {
                        stats.warn("nested_class_parse_failed:" + bounded(qualifiedName, 180));
                    }
                } else if (lower.endsWith(".jar")) {
                    stats.archivesDiscovered++;
                    if (depth >= MAX_NESTED_DEPTH || stats.archivesScanned >= MAX_NESTED_ARCHIVES) {
                        drainNestedEntry(zip, MAX_NESTED_ENTRY_BYTES, stats);
                        stats.warn("nested_jar_recursion_limit:" + bounded(qualifiedName, 180));
                        continue;
                    }
                    if (entry.getSize() > MAX_NESTED_ARCHIVE_BYTES) {
                        drainNestedEntry(zip, MAX_NESTED_ENTRY_BYTES, stats);
                        stats.warn("nested_jar_too_large:" + bounded(qualifiedName, 180));
                        continue;
                    }
                    byte[] deeperBytes = readNestedEntry(zip, MAX_NESTED_ARCHIVE_BYTES, stats);
                    if (stats.nestedArchiveBytes + deeperBytes.length > MAX_TOTAL_NESTED_ARCHIVE_BYTES) {
                        stats.warn("nested_jar_archive_byte_budget_exceeded");
                        continue;
                    }
                    stats.nestedArchiveBytes += deeperBytes.length;
                    scanNestedArchive(deeperBytes, qualifiedName, depth + 1, stats);
                } else {
                    drainNestedEntry(zip, MAX_NESTED_ENTRY_BYTES, stats);
                }
                zip.closeEntry();
            }
        } catch (IOException | RuntimeException e) {
            stats.warn("nested_jar_scan_stopped:" + bounded(archivePath, 180)
                    + ":" + bounded(e.getMessage(), 120));
            return;
        }
        if (!foundEntry) stats.warn("nested_jar_empty_or_invalid:" + bounded(archivePath, 180));
    }

    private static byte[] readNestedEntry(ZipInputStream zip, int maxBytes,
                                          NestedScanAccumulator stats) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        int entryBytes = 0;
        while ((read = zip.read(buffer)) != -1) {
            entryBytes += read;
            stats.uncompressedBytesScanned += read;
            if (entryBytes > maxBytes) throw new IOException("nested entry byte limit exceeded");
            if (stats.uncompressedBytesScanned > MAX_TOTAL_NESTED_UNCOMPRESSED_BYTES) {
                throw new IOException("nested total uncompressed byte budget exceeded");
            }
            out.write(buffer, 0, read);
        }
        return out.toByteArray();
    }

    private static void drainNestedEntry(ZipInputStream zip, int maxBytes,
                                         NestedScanAccumulator stats) throws IOException {
        byte[] buffer = new byte[8192];
        int read;
        int entryBytes = 0;
        while ((read = zip.read(buffer)) != -1) {
            entryBytes += read;
            stats.uncompressedBytesScanned += read;
            if (entryBytes > maxBytes) throw new IOException("nested entry byte limit exceeded");
            if (stats.uncompressedBytesScanned > MAX_TOTAL_NESTED_UNCOMPRESSED_BYTES) {
                throw new IOException("nested total uncompressed byte budget exceeded");
            }
        }
    }

    private static final class NestedScanAccumulator {
        private int archivesDiscovered;
        private int archivesScanned;
        private int entriesScanned;
        private int classesScanned;
        private long classBytesScanned;
        private long nestedArchiveBytes;
        private long uncompressedBytesScanned;
        private int evidenceOverflow;
        private int warningsOverflow;
        private final Map<String, Integer> protocolClassHits = new LinkedHashMap<>();
        private final List<Map<String, Object>> evidence = new ArrayList<>();
        private final List<String> warnings = new ArrayList<>();

        private void warn(String warning) {
            if (warnings.size() < MAX_WARNINGS_PER_JAR) warnings.add(warning);
            else warningsOverflow++;
        }
    }

    private static void addWarning(List<String> warnings, int[] overflow, String warning) {
        if (warnings.size() < MAX_WARNINGS_PER_JAR) warnings.add(warning);
        else overflow[0]++;
    }

    private static void detectPathSignals(String name, Map<String, Integer> formats,
                                          Map<String, Integer> resourceCounts,
                                          Map<String, Set<String>> namespaces,
                                          List<String> configSamples) {
        String lower = name.toLowerCase(Locale.ROOT);
        String format = null;
        if (lower.endsWith(".json")) format = "JSON";
        else if (lower.endsWith(".json5")) format = "JSON5";
        else if (lower.endsWith(".toml")) format = "TOML";
        else if (lower.endsWith(".properties")) format = "PROPERTIES";
        else if (lower.endsWith(".cfg") || lower.endsWith(".conf")) format = "CONFIG_TEXT";
        else if (lower.endsWith(".nbt")) format = "NBT_FILE";
        else if (lower.endsWith(".png")) format = "PNG";
        else if (lower.endsWith(".ogg")) format = "OGG";
        if (format != null) formats.merge(format, 1, Integer::sum);

        String[] parts = name.split("/");
        if (parts.length >= 2 && (parts[0].equals("assets") || parts[0].equals("data"))) {
            namespaces.computeIfAbsent(parts[0], ignored -> new LinkedHashSet<>()).add(parts[1]);
            if (parts.length >= 3) resourceCounts.merge(parts[0] + "/" + parts[2], 1, Integer::sum);
        }
        if ((lower.startsWith("config/") || lower.startsWith("defaultconfigs/")) && configSamples.size() < 200) {
            configSamples.add(name);
        }
    }

    private static Map<String, Object> safeMetadata(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (String key : List.of("id", "version", "name", "environment", "schemaVersion")) {
            Object value = source.get(key);
            if (value instanceof String || value instanceof Number || value instanceof Boolean) result.put(key, value);
        }
        Object depends = source.get("depends");
        if (depends instanceof Map<?, ?> map) {
            Map<String, Object> dependencies = new LinkedHashMap<>();
            map.forEach((key, value) -> {
                if (key instanceof String && (value instanceof String || value instanceof List<?>)) dependencies.put((String) key, value);
            });
            result.put("depends", dependencies);
        }
        return result;
    }

    private static Map<String, Object> parseTomlMetadata(String source) {
        Map<String, Object> result = new LinkedHashMap<>();
        List<String> ids = new ArrayList<>();
        List<Map<String, String>> modEntries = new ArrayList<>();
        Map<String, String> current = null;
        for (String rawLine : source.split("\\R")) {
            String line = rawLine.strip();
            if (line.startsWith("#") || line.isEmpty()) continue;
            if (line.equals("[[mods]]")) {
                current = new LinkedHashMap<>();
                modEntries.add(current);
                continue;
            }
            if (line.startsWith("[")) {
                current = null;
                continue;
            }
            if (current == null) continue;
            Matcher field = Pattern.compile("^([A-Za-z0-9_.-]+)\\s*=\\s*[\"']([^\"']*)[\"']\\s*(?:#.*)?$").matcher(line);
            if (field.matches()) current.put(field.group(1), field.group(2));
        }
        for (Map<String, String> mod : modEntries) {
            String id = mod.get("modId");
            if (id != null && !id.isBlank()) ids.add(id);
        }
        result.put("modIds", ids);
        result.put("modEntries", modEntries);
        result.put("metadataFormat", "BEST_EFFORT_MODS_SECTION_EXTRACTION");
        return result;
    }

    private static String readText(JarFile jar, JarEntry entry, int maxBytes) throws IOException {
        byte[] bytes = readBounded(jar.getInputStream(entry), maxBytes);
        if (bytes.length > maxBytes) throw new IOException("Metadata exceeds " + maxBytes + " bytes: " + entry.getName());
        return new String(bytes, StandardCharsets.UTF_8);
    }

    private static byte[] readBounded(InputStream input, int maxBytes) throws IOException {
        try (InputStream in = input; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int total = 0;
            int read;
            while ((read = in.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) return new byte[maxBytes + 1];
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        }
    }

    private static String sha256(Path path) throws IOException, NoSuchAlgorithmException {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = Files.newInputStream(path)) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = in.read(buffer)) != -1) digest.update(buffer, 0, read);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static String topLevel(String name) {
        int slash = name.indexOf('/');
        return slash < 0 ? "<root>" : name.substring(0, slash);
    }

    private static String bounded(String value, int max) {
        if (value == null) return "unspecified";
        return value.length() <= max ? value : value.substring(0, max);
    }
}
