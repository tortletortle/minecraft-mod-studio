package dev.tortletortle.mms.umpd;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Small dependency-free JSON parser/writer for untrusted mod metadata and reports. */
final class MiniJson {
    private MiniJson() {}

    static Object parse(String source) {
        Parser parser = new Parser(source);
        Object value = parser.value();
        parser.space();
        if (!parser.end()) throw parser.error("Trailing content");
        return value;
    }

    static String stringify(Object value) {
        StringBuilder out = new StringBuilder();
        write(value, out);
        return out.toString();
    }

    private static void write(Object value, StringBuilder out) {
        if (value == null) out.append("null");
        else if (value instanceof String s) quote(s, out);
        else if (value instanceof Number || value instanceof Boolean) out.append(value);
        else if (value instanceof Map<?, ?> map) {
            out.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!first) out.append(',');
                first = false;
                quote(String.valueOf(entry.getKey()), out);
                out.append(':');
                write(entry.getValue(), out);
            }
            out.append('}');
        } else if (value instanceof Iterable<?> values) {
            out.append('[');
            boolean first = true;
            for (Object item : values) {
                if (!first) out.append(',');
                first = false;
                write(item, out);
            }
            out.append(']');
        } else quote(String.valueOf(value), out);
    }

    private static void quote(String value, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
                }
            }
        }
        out.append('"');
    }

    private static final class Parser {
        private final String source;
        private int at;

        private Parser(String source) { this.source = source; }
        private boolean end() { return at >= source.length(); }
        private IllegalArgumentException error(String message) {
            return new IllegalArgumentException(message + " at character " + at);
        }
        private void space() {
            while (!end() && Character.isWhitespace(source.charAt(at))) at++;
        }
        private char take() {
            if (end()) throw error("Unexpected end");
            return source.charAt(at++);
        }
        private boolean consume(char c) {
            space();
            if (!end() && source.charAt(at) == c) { at++; return true; }
            return false;
        }
        private Object value() {
            space();
            if (end()) throw error("Expected value");
            return switch (source.charAt(at)) {
                case '{' -> object();
                case '[' -> array();
                case '"' -> string();
                case 't' -> literal("true", Boolean.TRUE);
                case 'f' -> literal("false", Boolean.FALSE);
                case 'n' -> literal("null", null);
                default -> number();
            };
        }
        private Map<String, Object> object() {
            take();
            Map<String, Object> result = new LinkedHashMap<>();
            if (consume('}')) return result;
            do {
                space();
                if (end() || source.charAt(at) != '"') throw error("Expected object key");
                String key = string();
                if (!consume(':')) throw error("Expected ':'");
                result.put(key, value());
                if (consume('}')) return result;
                if (!consume(',')) throw error("Expected ',' or '}'");
            } while (true);
        }
        private List<Object> array() {
            take();
            List<Object> result = new ArrayList<>();
            if (consume(']')) return result;
            do {
                result.add(value());
                if (consume(']')) return result;
                if (!consume(',')) throw error("Expected ',' or ']'");
            } while (true);
        }
        private String string() {
            if (take() != '"') throw error("Expected string");
            StringBuilder out = new StringBuilder();
            while (!end()) {
                char c = take();
                if (c == '"') return out.toString();
                if (c != '\\') {
                    if (c < 0x20) throw error("Control character in string");
                    out.append(c);
                    continue;
                }
                char escaped = take();
                switch (escaped) {
                    case '"', '\\', '/' -> out.append(escaped);
                    case 'b' -> out.append('\b');
                    case 'f' -> out.append('\f');
                    case 'n' -> out.append('\n');
                    case 'r' -> out.append('\r');
                    case 't' -> out.append('\t');
                    case 'u' -> {
                        if (at + 4 > source.length()) throw error("Incomplete unicode escape");
                        try { out.append((char) Integer.parseInt(source.substring(at, at + 4), 16)); }
                        catch (NumberFormatException e) { throw error("Invalid unicode escape"); }
                        at += 4;
                    }
                    default -> throw error("Invalid escape");
                }
            }
            throw error("Unterminated string");
        }
        private Object literal(String token, Object result) {
            if (!source.startsWith(token, at)) throw error("Invalid literal");
            at += token.length();
            return result;
        }
        private Number number() {
            int start = at;
            if (!end() && source.charAt(at) == '-') at++;
            if (end() || !Character.isDigit(source.charAt(at))) throw error("Invalid number");
            if (source.charAt(at) == '0') at++;
            else while (!end() && Character.isDigit(source.charAt(at))) at++;
            if (!end() && source.charAt(at) == '.') {
                at++;
                if (end() || !Character.isDigit(source.charAt(at))) throw error("Invalid fraction");
                while (!end() && Character.isDigit(source.charAt(at))) at++;
            }
            if (!end() && (source.charAt(at) == 'e' || source.charAt(at) == 'E')) {
                at++;
                if (!end() && (source.charAt(at) == '+' || source.charAt(at) == '-')) at++;
                if (end() || !Character.isDigit(source.charAt(at))) throw error("Invalid exponent");
                while (!end() && Character.isDigit(source.charAt(at))) at++;
            }
            String token = source.substring(start, at);
            try {
                BigDecimal decimal = new BigDecimal(token);
                try { return decimal.longValueExact(); }
                catch (ArithmeticException ignored) { return decimal; }
            } catch (NumberFormatException e) { throw error("Invalid number"); }
        }
    }
}
