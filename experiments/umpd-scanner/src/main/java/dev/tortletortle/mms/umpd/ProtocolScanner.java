package dev.tortletortle.mms.umpd;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitOption;
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
    private final ClassFileSignatureScanner classScanner = new ClassFileSignatureScanner();

    public static void main(String[] args) throws Exception {
        if (args.length < 2 || !"scan".equals(args[0])) {
            System.err.println("Usage: umpd scan <mods-directory> [--out <report.json>]");
            System.exit(2);
        }
        Path input = Path.of(args[1]).toAbsolutePath().normalize();
        Path output = null;
        for (int i = 2; i < args.length; i++) {
            if ("--out".equals(args[i]) && i + 1 < args.length) output = Path.of(args[++i]).toAbsolutePath().normalize();
            else throw new IllegalArgumentException("Unknown argument: " + args[i]);
        }
        if (output != null && output.startsWith(input)) {
            throw new IllegalArgumentException("Report output must be outside the scanned mods directory");
        }
        ProtocolScanner scanner = new ProtocolScanner();
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

    public Map<String, Object> scanDirectory(Path directory) throws IOException {
        if (!Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS)) {
            throw new IOException("Input is not a directory: " + directory);
        }
        List<Path> jars;
        try (Stream<Path> walk = Files.walk(directory, FileVisitOption.values())) {
            jars = walk.filter(path -> Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
                    .filter(path -> path.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".jar"))
                    .sorted(Comparator.comparing(path -> directory.relativize(path).toString()))
                    .limit(MAX_JARS + 1L).toList();
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
                    warnings.add("entry_limit_exceeded");
                    break;
                }
                String name = entry.getName();
                entryCounts.merge(topLevel(name), 1, Integer::sum);
                detectPathSignals(name, formatCounts, resourcePathCounts, resourceNamespaces, configPathSamples);
                if (name.toLowerCase(Locale.ROOT).endsWith(".jar")) {
                    entryCounts.merge("<nested-jar>", 1, Integer::sum);
                    if (nestedJarSamples.size() < 100) nestedJarSamples.add(name);
                }

                if (name.equals("fabric.mod.json")) {
                    String text = readText(jar, entry, MAX_METADATA_BYTES);
                    Object parsed = MiniJson.parse(text);
                    if (parsed instanceof Map<?, ?> map) {
                        metadata.put("fabric", safeMetadata(map));
                        Object id = map.get("id");
                        if (id instanceof String value) modIds.add(value);
                        loader = "FABRIC";
                    } else warnings.add("fabric_mod_json_root_not_object");
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
                        warnings.add("class_too_large:" + bounded(name, 180));
                        continue;
                    }
                    if (entry.getSize() > 0 && classBytesScanned + entry.getSize() > MAX_TOTAL_CLASS_BYTES_PER_JAR) {
                        warnings.add("class_byte_budget_exceeded");
                        continue;
                    }
                    byte[] bytes = readBounded(jar.getInputStream(entry), MAX_CLASS_BYTES);
                    if (bytes.length > MAX_CLASS_BYTES) {
                        warnings.add("class_too_large:" + bounded(name, 180));
                        continue;
                    }
                    if (classBytesScanned + bytes.length > MAX_TOTAL_CLASS_BYTES_PER_JAR) {
                        warnings.add("class_byte_budget_exceeded");
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
                                item.put("evidenceLevel", "CLASS_TYPE_OR_MEMBER_REFERENCE");
                                item.put("classPath", name);
                                item.put("signals", hit.getValue());
                                evidence.add(item);
                            } else evidenceOverflow++;
                        }
                    } catch (IOException e) {
                        warnings.add("class_parse_failed:" + bounded(name, 180));
                    }
                }
            }
        }
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
        artifact.put("classEntriesSeen", classEntriesSeen);
        artifact.put("classesScanned", classesScanned);
        artifact.put("classBytesScanned", classBytesScanned);
        artifact.put("protocolClassHitCounts", protocolClassHits);
        artifact.put("protocols", new ArrayList<>(protocolClassHits.keySet()));
        artifact.put("protocolEvidence", evidence);
        artifact.put("evidenceOverflow", evidenceOverflow);
        artifact.put("warnings", warnings);
        artifact.put("entriesScanned", entriesScanned);
        return artifact;
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
