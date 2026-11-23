package dev.tortletortle.mms.umpd;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.FilterInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Minimal Tiny v2 class-name namespace adapter. It deliberately does not remap fields or methods. */
final class TinyV2Mappings {
    static final long MAX_MAPPING_FILE_BYTES = 128L * 1024 * 1024;

    record Mapping(String fromNamespace, String toNamespace, Map<String, String> classNames,
                   String sha256, String sourcePath) {
        Mapping {
            classNames = Map.copyOf(classNames);
        }

        static Mapping none() {
            return new Mapping("none", "none", Map.of(), "", "none");
        }

        String mapClass(String internalName) {
            return classNames.getOrDefault(internalName, internalName);
        }
    }

    private TinyV2Mappings() {}

    static Mapping load(Path path, String fromNamespace, String toNamespace) throws IOException {
        if (!Files.isRegularFile(path)) throw new IOException("Mapping file does not exist: " + path);
        long size = Files.size(path);
        if (size <= 0 || size > MAX_MAPPING_FILE_BYTES) {
            throw new IOException("Tiny mapping file size must be between 1 byte and 128 MiB");
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var bounded = new BoundedInputStream(Files.newInputStream(path), MAX_MAPPING_FILE_BYTES);
                 var input = new DigestInputStream(bounded, digest);
                 Reader reader = new InputStreamReader(input, StandardCharsets.UTF_8)) {
                Mapping parsed = parse(reader, fromNamespace, toNamespace);
                String sha256 = HexFormat.of().formatHex(digest.digest());
                return new Mapping(parsed.fromNamespace(), parsed.toNamespace(), parsed.classNames(),
                        sha256, path.toAbsolutePath().normalize().toString());
            }
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
    }

    static Mapping parse(Reader source, String fromNamespace, String toNamespace) throws IOException {
        if (fromNamespace == null || fromNamespace.isBlank()
                || toNamespace == null || toNamespace.isBlank()
                || fromNamespace.equals(toNamespace)) {
            throw new IllegalArgumentException("Distinct source and target namespaces are required");
        }
        try (BufferedReader reader = source instanceof BufferedReader buffered ? buffered : new BufferedReader(source)) {
            String headerLine = reader.readLine();
            if (headerLine == null) throw new IOException("Tiny mapping file is empty");
            if (headerLine.startsWith("\uFEFF")) headerLine = headerLine.substring(1);
            String[] header = headerLine.split("\t", -1);
            if (header.length < 5 || !"tiny".equals(header[0]) || !"2".equals(header[1])) {
                throw new IOException("Expected a Tiny v2 header");
            }
            try {
                if (Integer.parseInt(header[2]) < 0) throw new NumberFormatException("negative minor version");
            } catch (NumberFormatException invalidMinor) {
                throw new IOException("Invalid Tiny v2 minor version", invalidMinor);
            }

            List<String> namespaces = List.of(header).subList(3, header.length);
            Set<String> uniqueNamespaces = new HashSet<>();
            for (String namespace : namespaces) {
                if (namespace.isEmpty() || !uniqueNamespaces.add(namespace)) {
                    throw new IOException("Tiny v2 namespace names must be non-empty and unique");
                }
            }
            int fromIndex = namespaces.indexOf(fromNamespace);
            int toIndex = namespaces.indexOf(toNamespace);
            if (fromIndex < 0 || toIndex < 0) {
                throw new IOException("Tiny v2 namespaces not found. Available: " + String.join(", ", namespaces));
            }

            Map<String, String> classNames = new LinkedHashMap<>();
            boolean escapedNames = false;
            boolean sawClass = false;
            String line;
            int lineNumber = 1;
            while ((line = reader.readLine()) != null) {
                lineNumber++;
                if (line.length() > 1024 * 1024) {
                    throw new IOException("Tiny mapping line exceeds 1 MiB at line " + lineNumber);
                }
                if (line.isBlank() || line.stripLeading().startsWith("#")) continue;
                int indentation = leadingTabs(line);
                String[] parts = line.split("\t", -1);

                if (indentation == 1 && !sawClass && parts.length > 1 && "escaped-names".equals(parts[1])) {
                    escapedNames = true;
                    continue;
                }
                if (indentation != 0 || parts.length == 0 || !"c".equals(parts[0])) continue;
                sawClass = true;

                int fromColumn = 1 + fromIndex;
                int toColumn = 1 + toIndex;
                if (parts.length != header.length - 2 || parts.length <= Math.max(fromColumn, toColumn)) {
                    throw new IOException("Malformed class mapping column count at line " + lineNumber);
                }
                String sourceName = parts[fromColumn];
                String targetName = parts[toColumn];
                if (escapedNames) {
                    sourceName = unescape(sourceName, lineNumber);
                    targetName = unescape(targetName, lineNumber);
                }
                if (sourceName.isEmpty() || targetName.isEmpty()) continue;
                if (classNames.containsKey(sourceName)) {
                    throw new IOException("Duplicate class mapping at line " + lineNumber + ": " + sourceName);
                }
                classNames.put(sourceName, targetName);
            }
            // A valid Tiny file may have no useful names for this namespace pair.
            // Empty destination cells mean identity mapping and therefore need no map entry.
            return new Mapping(fromNamespace, toNamespace, classNames, "in-memory", "<reader>");
        }
    }

    private static final class BoundedInputStream extends FilterInputStream {
        private final long maximumBytes;
        private long bytesRead;

        private BoundedInputStream(InputStream input, long maximumBytes) {
            super(input);
            this.maximumBytes = maximumBytes;
        }

        @Override
        public int read() throws IOException {
            int value = super.read();
            if (value != -1 && ++bytesRead > maximumBytes) {
                throw new IOException("Tiny mapping file exceeds the 128 MiB read budget");
            }
            return value;
        }

        @Override
        public int read(byte[] buffer, int offset, int length) throws IOException {
            int read = super.read(buffer, offset, (int) Math.min(length, maximumBytes - bytesRead + 1));
            if (read > 0) {
                bytesRead += read;
                if (bytesRead > maximumBytes) throw new IOException("Tiny mapping file exceeds the 128 MiB read budget");
            }
            return read;
        }
    }

    private static int leadingTabs(String line) {
        int count = 0;
        while (count < line.length() && line.charAt(count) == '\t') count++;
        return count;
    }

    private static String unescape(String value, int lineNumber) throws IOException {
        StringBuilder result = new StringBuilder(value.length());
        for (int i = 0; i < value.length(); i++) {
            char current = value.charAt(i);
            if (current != '\\') {
                result.append(current);
                continue;
            }
            if (++i >= value.length()) throw new IOException("Incomplete Tiny escape at line " + lineNumber);
            char escaped = value.charAt(i);
            switch (escaped) {
                case '\\' -> result.append('\\');
                case 'n' -> result.append('\n');
                case 'r' -> result.append('\r');
                case 't' -> result.append('\t');
                case '0' -> result.append('\0');
                default -> throw new IOException("Unknown Tiny escape at line " + lineNumber);
            }
        }
        return result.toString();
    }
}
