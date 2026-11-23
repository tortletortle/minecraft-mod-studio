package dev.tortletortle.mms.umpd;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Minimal Tiny v2 class-name namespace adapter. It deliberately does not remap fields or methods. */
final class TinyV2Mappings {
    static final long MAX_MAPPING_FILE_BYTES = 512L * 1024 * 1024;

    record Mapping(String fromNamespace, String toNamespace, Map<String, String> classNames,
                   String sha256, String sourcePath) {
        Mapping {
            classNames = Map.copyOf(classNames);
        }

        static Mapping none() {
            return new Mapping("none", "none", Map.of(), "", "none");
        }

        String mapClass(String internalName) {
            String direct = classNames.get(internalName);
            if (direct != null) return direct;
            int nested = internalName.indexOf('
    }

    private TinyV2Mappings() {}

    static Mapping load(Path path, String fromNamespace, String toNamespace) throws IOException {
        if (!Files.isRegularFile(path)) throw new IOException("Mapping file does not exist: " + path);
        long size = Files.size(path);
        if (size <= 0 || size > MAX_MAPPING_FILE_BYTES) {
            throw new IOException("Tiny mapping file size must be between 1 byte and 512 MiB");
        }
        String sha256;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var input = Files.newInputStream(path)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) != -1) digest.update(buffer, 0, read);
            }
            sha256 = HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
        try (Reader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            Mapping parsed = parse(reader, fromNamespace, toNamespace);
            return new Mapping(parsed.fromNamespace(), parsed.toNamespace(), parsed.classNames(),
                    sha256, path.toAbsolutePath().normalize().toString());
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

            List<String> namespaces = List.of(header).subList(3, header.length);
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
                if (parts.length <= Math.max(fromColumn, toColumn)) {
                    throw new IOException("Malformed class mapping at line " + lineNumber);
                }
                String sourceName = parts[fromColumn];
                String targetName = parts[toColumn];
                if (escapedNames) {
                    sourceName = unescape(sourceName, lineNumber);
                    targetName = unescape(targetName, lineNumber);
                }
                if (sourceName.isEmpty() || targetName.isEmpty()) continue;
                String previous = classNames.putIfAbsent(sourceName, targetName);
                if (previous != null && !previous.equals(targetName)) {
                    throw new IOException("Conflicting class mapping at line " + lineNumber + ": " + sourceName);
                }
            }
            if (classNames.isEmpty()) throw new IOException("Tiny v2 file contains no class mappings for the selected namespaces");
            return new Mapping(fromNamespace, toNamespace, classNames, "in-memory", "<reader>");
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
);
            while (nested > 0) {
                String mappedOuter = classNames.get(internalName.substring(0, nested));
                if (mappedOuter != null) return mappedOuter + internalName.substring(nested);
                nested = internalName.indexOf('
    }

    private TinyV2Mappings() {}

    static Mapping load(Path path, String fromNamespace, String toNamespace) throws IOException {
        if (!Files.isRegularFile(path)) throw new IOException("Mapping file does not exist: " + path);
        long size = Files.size(path);
        if (size <= 0 || size > MAX_MAPPING_FILE_BYTES) {
            throw new IOException("Tiny mapping file size must be between 1 byte and 512 MiB");
        }
        String sha256;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var input = Files.newInputStream(path)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) != -1) digest.update(buffer, 0, read);
            }
            sha256 = HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
        try (Reader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            Mapping parsed = parse(reader, fromNamespace, toNamespace);
            return new Mapping(parsed.fromNamespace(), parsed.toNamespace(), parsed.classNames(),
                    sha256, path.toAbsolutePath().normalize().toString());
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

            List<String> namespaces = List.of(header).subList(3, header.length);
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
                if (parts.length <= Math.max(fromColumn, toColumn)) {
                    throw new IOException("Malformed class mapping at line " + lineNumber);
                }
                String sourceName = parts[fromColumn];
                String targetName = parts[toColumn];
                if (escapedNames) {
                    sourceName = unescape(sourceName, lineNumber);
                    targetName = unescape(targetName, lineNumber);
                }
                if (sourceName.isEmpty() || targetName.isEmpty()) continue;
                String previous = classNames.putIfAbsent(sourceName, targetName);
                if (previous != null && !previous.equals(targetName)) {
                    throw new IOException("Conflicting class mapping at line " + lineNumber + ": " + sourceName);
                }
            }
            if (classNames.isEmpty()) throw new IOException("Tiny v2 file contains no class mappings for the selected namespaces");
            return new Mapping(fromNamespace, toNamespace, classNames, "in-memory", "<reader>");
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
, nested + 1);
            }
            return internalName;
        }
    }

    private TinyV2Mappings() {}

    static Mapping load(Path path, String fromNamespace, String toNamespace) throws IOException {
        if (!Files.isRegularFile(path)) throw new IOException("Mapping file does not exist: " + path);
        long size = Files.size(path);
        if (size <= 0 || size > MAX_MAPPING_FILE_BYTES) {
            throw new IOException("Tiny mapping file size must be between 1 byte and 512 MiB");
        }
        String sha256;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var input = Files.newInputStream(path)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) != -1) digest.update(buffer, 0, read);
            }
            sha256 = HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
        try (Reader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            Mapping parsed = parse(reader, fromNamespace, toNamespace);
            return new Mapping(parsed.fromNamespace(), parsed.toNamespace(), parsed.classNames(),
                    sha256, path.toAbsolutePath().normalize().toString());
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

            List<String> namespaces = List.of(header).subList(3, header.length);
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
                if (parts.length <= Math.max(fromColumn, toColumn)) {
                    throw new IOException("Malformed class mapping at line " + lineNumber);
                }
                String sourceName = parts[fromColumn];
                String targetName = parts[toColumn];
                if (escapedNames) {
                    sourceName = unescape(sourceName, lineNumber);
                    targetName = unescape(targetName, lineNumber);
                }
                if (sourceName.isEmpty() || targetName.isEmpty()) continue;
                String previous = classNames.putIfAbsent(sourceName, targetName);
                if (previous != null && !previous.equals(targetName)) {
                    throw new IOException("Conflicting class mapping at line " + lineNumber + ": " + sourceName);
                }
            }
            if (classNames.isEmpty()) throw new IOException("Tiny v2 file contains no class mappings for the selected namespaces");
            return new Mapping(fromNamespace, toNamespace, classNames, "in-memory", "<reader>");
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
