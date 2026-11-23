package dev.mms.livedebugger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import java.io.IOException;
import org.junit.jupiter.api.Test;

final class CommandManifestJsonParserTest {
    @Test
    void acceptsStrictUtf8JsonDocument() throws IOException {
        JsonObject document = CommandManifestRegistry.parseStrictJson(
                "{\"schemaVersion\":1,\"description\":\"中文命令\"}")
                .getAsJsonObject();

        assertEquals(1, document.get("schemaVersion").getAsInt());
        assertEquals("中文命令", document.get("description").getAsString());
    }

    @Test
    void rejectsDuplicateObjectKeys() {
        assertThrows(JsonParseException.class, () ->
                CommandManifestRegistry.parseStrictJson(
                        "{\"schemaVersion\":1,\"schemaVersion\":2}"));
    }

    @Test
    void rejectsLenientNonJsonSyntax() {
        assertThrows(Exception.class, () ->
                CommandManifestRegistry.parseStrictJson("{schemaVersion:1}"));
        assertThrows(Exception.class, () ->
                CommandManifestRegistry.parseStrictJson("{\"schemaVersion\":1,}"));
    }

    @Test
    void rejectsExcessiveNestingBeforeRecursiveParsingCanOverflow() {
        String nested = "[".repeat(17) + "0" + "]".repeat(17);
        assertThrows(Exception.class, () -> CommandManifestRegistry.parseStrictJson(nested));
    }

    @Test
    void rejectsMultipleTopLevelValues() {
        assertThrows(Exception.class, () ->
                CommandManifestRegistry.parseStrictJson("{\"schemaVersion\":1} {\"schemaVersion\":2}"));
    }

    @Test
    void rejectsUnescapedControlCharactersInsideStrings() {
        String invalid = "{\"description\":\"before" + (char) 1 + "after\"}";
        assertThrows(Exception.class, () -> CommandManifestRegistry.parseStrictJson(invalid));
    }
}
