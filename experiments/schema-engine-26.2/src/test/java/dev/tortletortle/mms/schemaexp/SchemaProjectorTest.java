package dev.tortletortle.mms.schemaexp;

import com.mojang.serialization.Codec;
import net.mehvahdjukaar.codecui.Schema;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

class SchemaProjectorTest {
    @Test
    void projectsPrimitiveBounds() {
        var document = new SchemaProjector().project(new Schema.IntRange(0, 64));
        var root = document.getAsJsonObject("root");

        assertEquals(1, document.get("projectionVersion").getAsInt());
        assertEquals("integer", root.get("kind").getAsString());
        assertEquals(0, root.get("min").getAsInt());
        assertEquals(64, root.get("max").getAsInt());
    }

    @Test
    void preservesRecordFieldMetadataAndSafeDefaults() {
        Schema.Record<Object> schema = new Schema.Record<>(Object.class, List.of(
                new Schema.Field<Object, String>("name", new Schema.Str(1, 24, null), false, null),
                new Schema.Field<Object, Integer>("damage", new Schema.IntRange(0, 64), true, 12)
        ));

        var root = new SchemaProjector().project(schema).getAsJsonObject("root");
        var fields = root.getAsJsonArray("fields");

        assertEquals("record", root.get("kind").getAsString());
        assertEquals(2, fields.size());
        assertEquals("name", fields.get(0).getAsJsonObject().get("name").getAsString());
        assertFalse(fields.get(0).getAsJsonObject().get("optional").getAsBoolean());
        assertEquals(12, fields.get(1).getAsJsonObject().get("default").getAsInt());
        assertTrue(fields.get(1).getAsJsonObject().get("optional").getAsBoolean());
    }

    @Test
    void recursiveReferenceBecomesReferenceInsteadOfInfiniteExpansion() {
        Schema.Ref<Object> next = new Schema.Ref<>();
        Schema.Record<Object> node = new Schema.Record<>(Object.class, List.of(
                new Schema.Field<Object, Object>("next", next, true, null)
        ));
        next.bind(node);

        var root = new SchemaProjector().project(node).getAsJsonObject("root");
        var childSchema = root.getAsJsonArray("fields")
                .get(0).getAsJsonObject().getAsJsonObject("schema");

        assertEquals(root.get("$id").getAsString(), childSchema.get("$ref").getAsString());
    }

    @Test
    void opaqueCodecIsMarkedAsRawJsonAndCodecObjectIsNotSerialized() {
        Schema.Opaque<String> opaque = new Schema.Opaque<>(Codec.STRING, null);

        var root = new SchemaProjector().project(opaque).getAsJsonObject("root");

        assertEquals("opaque", root.get("kind").getAsString());
        assertEquals("raw_json", root.get("fallback").getAsString());
        assertTrue(root.has("codecClass"));
        assertFalse(root.has("codec"));
    }

    @Test
    void projectionDoesNotExecuteEnumLabelCallbacks() {
        AtomicInteger callbackCount = new AtomicInteger();
        Schema.Enum<String> enumeration = new Schema.Enum<>(List.of("stone"), value -> {
            callbackCount.incrementAndGet();
            return value;
        });

        var root = new SchemaProjector().project(enumeration).getAsJsonObject("root");

        assertEquals(0, callbackCount.get());
        assertEquals("stone", root.getAsJsonArray("options").get(0).getAsJsonObject()
                .get("label").getAsString());
    }

    @Test
    void collectionProjectionHasAnExplicitItemLimit() {
        List<Schema.Field<Object, ?>> fields = new ArrayList<>();
        for (int i = 0; i < 600; i++) {
            fields.add(new Schema.Field<Object, Integer>("field_" + i, new Schema.IntRange(0, 10), false, null));
        }
        Schema.Record<Object> schema = new Schema.Record<>(Object.class, fields);

        var root = new SchemaProjector().project(schema).getAsJsonObject("root");

        assertEquals(512, root.getAsJsonArray("fields").size());
        assertTrue(root.get("fieldsTruncated").getAsBoolean());
    }

    @Test
    void projectionStopsAtConfiguredNodeBudget() {
        Schema.Record<Object> schema = new Schema.Record<>(Object.class, List.of(
                new Schema.Field<Object, Integer>("first", new Schema.IntRange(0, 10), false, null),
                new Schema.Field<Object, String>("second", new Schema.Str(0, 20, null), false, null)
        ));

        var document = new SchemaProjector(32, 2).project(schema);
        var root = document.getAsJsonObject("root");
        var fields = root.getAsJsonArray("fields");

        assertEquals(2, document.get("nodeCount").getAsInt());
        assertEquals("truncated", fields.get(1).getAsJsonObject()
                .getAsJsonObject("schema").get("kind").getAsString());
        assertEquals("max_nodes", fields.get(1).getAsJsonObject()
                .getAsJsonObject("schema").get("reason").getAsString());
    }

    @Test
    void projectionStopsAtConfiguredDepthBudget() {
        Schema<?> nested = new Schema.Bool();
        for (int i = 0; i < 5; i++) {
            nested = new Schema.ListOf<>(nested, 0, 4);
        }

        var root = new SchemaProjector(2, 100).project(nested).getAsJsonObject("root");
        var cursor = root;
        int visitedLists = 0;
        while ("list".equals(cursor.get("kind").getAsString())) {
            visitedLists++;
            cursor = cursor.getAsJsonObject("element");
        }

        assertEquals("truncated", cursor.get("kind").getAsString());
        assertEquals("max_depth", cursor.get("reason").getAsString());
        assertTrue(visitedLists <= 3);
    }
}
