package dev.tortletortle.mms.schemaexp;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.mehvahdjukaar.codecui.Schema;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Converts CodecUI's runtime schema graph into a bounded, versioned JSON DTO.
 *
 * It deliberately does not serialize Codec instances, invoke DispatchedMapOf's
 * per-key resolver, or inspect arbitrary widget/codec internals.
 */
public final class SchemaProjector {
    public static final int PROJECTION_VERSION = 1;

    private final int maxDepth;
    private final int maxNodes;

    public SchemaProjector() {
        this(32, 2_048);
    }

    public SchemaProjector(int maxDepth, int maxNodes) {
        if (maxDepth < 1 || maxNodes < 1) {
            throw new IllegalArgumentException("Projection limits must be positive");
        }
        this.maxDepth = maxDepth;
        this.maxNodes = maxNodes;
    }

    public JsonObject project(Schema<?> root) {
        Context context = new Context();
        JsonObject document = new JsonObject();
        document.addProperty("projectionVersion", PROJECTION_VERSION);
        document.add("root", context.visit(root, 0));
        document.addProperty("nodeCount", context.nodes);
        document.addProperty("maxDepth", maxDepth);
        document.addProperty("maxNodes", maxNodes);
        return document;
    }

    public static String kindOf(Schema<?> schema) {
        if (schema instanceof Schema.Bool) return "boolean";
        if (schema instanceof Schema.IntRange) return "integer";
        if (schema instanceof Schema.LongRange) return "long";
        if (schema instanceof Schema.FloatRange || schema instanceof Schema.DoubleRange) return "number";
        if (schema instanceof Schema.Str) return "string";
        if (schema instanceof Schema.ResourceId) return "resource_id";
        if (schema instanceof Schema.TagId) return "tag_id";
        if (schema instanceof Schema.Enum<?>) return "enum";
        if (schema instanceof Schema.Record<?>) return "record";
        if (schema instanceof Schema.ListOf<?>) return "list";
        if (schema instanceof Schema.MapOf<?, ?>) return "map";
        if (schema instanceof Schema.DispatchedMapOf<?, ?>) return "dispatched_map";
        if (schema instanceof Schema.AnyOf<?>) return "any_of";
        if (schema instanceof Schema.PairOf<?, ?>) return "pair";
        if (schema instanceof Schema.OneOf<?>) return "one_of";
        if (schema instanceof Schema.Ref<?>) return "ref";
        if (schema instanceof Schema.Opaque<?>) return "opaque";
        if (schema instanceof Schema.Custom<?>) return "custom";
        return "unsupported";
    }

    private final class Context {
        private final IdentityHashMap<Schema<?>, String> ids = new IdentityHashMap<>();
        private final Set<Schema<?>> resolvingRefs =
                Collections.newSetFromMap(new IdentityHashMap<>());
        private int nodes;

        private JsonObject visit(Schema<?> schema, int depth) {
            if (schema == null) return marker("unresolved", "null_schema");
            if (depth > maxDepth) return marker("truncated", "max_depth");

            if (schema instanceof Schema.Ref<?> ref) {
                Schema<?> target = ref.target();
                if (target == null) return marker("unresolved_ref", "target_not_bound");
                if (!resolvingRefs.add(schema)) return marker("unresolved_ref", "reference_cycle");
                try {
                    return visit(target, depth);
                } finally {
                    resolvingRefs.remove(schema);
                }
            }

            String existingId = ids.get(schema);
            if (existingId != null) {
                JsonObject reference = new JsonObject();
                reference.addProperty("$ref", existingId);
                return reference;
            }
            if (nodes >= maxNodes) return marker("truncated", "max_nodes");

            String id = "s" + (++nodes);
            ids.put(schema, id);

            JsonObject out = new JsonObject();
            out.addProperty("$id", id);

            if (schema instanceof Schema.Bool) {
                out.addProperty("kind", "boolean");
            } else if (schema instanceof Schema.IntRange value) {
                out.addProperty("kind", "integer");
                out.addProperty("min", value.min());
                out.addProperty("max", value.max());
            } else if (schema instanceof Schema.LongRange value) {
                out.addProperty("kind", "long");
                out.addProperty("min", value.min());
                out.addProperty("max", value.max());
            } else if (schema instanceof Schema.FloatRange value) {
                out.addProperty("kind", "number");
                out.addProperty("numberType", "float");
                out.addProperty("min", value.min());
                out.addProperty("max", value.max());
            } else if (schema instanceof Schema.DoubleRange value) {
                out.addProperty("kind", "number");
                out.addProperty("numberType", "double");
                out.addProperty("min", value.min());
                out.addProperty("max", value.max());
            } else if (schema instanceof Schema.Str value) {
                out.addProperty("kind", "string");
                out.addProperty("minLength", value.minLen());
                out.addProperty("maxLength", value.maxLen());
                if (value.pattern() != null) out.addProperty("pattern", safeText(value.pattern().pattern()));
            } else if (schema instanceof Schema.ResourceId value) {
                out.addProperty("kind", "resource_id");
                out.addProperty("registryConstrained", value.registry() != null);
            } else if (schema instanceof Schema.TagId value) {
                out.addProperty("kind", "tag_id");
                out.addProperty("registryConstrained", value.registry() != null);
                out.addProperty("hashed", value.hashed());
            } else if (schema instanceof Schema.Enum<?> value) {
                out.addProperty("kind", "enum");
                JsonArray options = new JsonArray();
                int index = 0;
                for (Object option : value.options()) {
                    JsonObject item = new JsonObject();
                    item.addProperty("label", enumLabel(value, option, index));
                    addSafeScalar(item, "value", option);
                    options.add(item);
                    index++;
                    if (index >= 512) break;
                }
                out.add("options", options);
                if (value.options().size() > 512) out.addProperty("optionsTruncated", true);
            } else if (schema instanceof Schema.Record<?> value) {
                out.addProperty("kind", "record");
                out.addProperty("javaType", value.type().getName());
                JsonArray fields = new JsonArray();
                for (Schema.Field<?, ?> field : value.fields()) {
                    JsonObject item = new JsonObject();
                    item.addProperty("name", safeText(field.name()));
                    item.addProperty("optional", field.optional());
                    item.addProperty("inline", field.inline());
                    if (field.defaultValue() != null) addSafeScalar(item, "default", field.defaultValue());
                    item.add("schema", visit(field.schema(), depth + 1));
                    fields.add(item);
                }
                out.add("fields", fields);
            } else if (schema instanceof Schema.ListOf<?> value) {
                out.addProperty("kind", "list");
                out.addProperty("minItems", value.min());
                out.addProperty("maxItems", value.max());
                out.add("element", visit(value.element(), depth + 1));
            } else if (schema instanceof Schema.MapOf<?, ?> value) {
                out.addProperty("kind", "map");
                out.add("key", visit(value.key(), depth + 1));
                out.add("value", visit(value.value(), depth + 1));
            } else if (schema instanceof Schema.DispatchedMapOf<?, ?> value) {
                out.addProperty("kind", "dispatched_map");
                out.addProperty("valueSchemaMode", "resolved_per_key");
                out.add("key", visit(value.key(), depth + 1));
            } else if (schema instanceof Schema.AnyOf<?> value) {
                out.addProperty("kind", "any_of");
                JsonArray options = new JsonArray();
                for (Schema.AnyOf.Option option : value.options()) {
                    JsonObject item = new JsonObject();
                    if (option.label() != null) item.addProperty("label", safeText(option.label()));
                    item.add("schema", visit(option.schema(), depth + 1));
                    options.add(item);
                }
                out.add("options", options);
            } else if (schema instanceof Schema.PairOf<?, ?> value) {
                out.addProperty("kind", "pair");
                out.add("first", visit(value.first(), depth + 1));
                out.add("second", visit(value.second(), depth + 1));
            } else if (schema instanceof Schema.OneOf<?> value) {
                out.addProperty("kind", "one_of");
                out.addProperty("typeField", safeText(value.typeField()));
                if (value.valueField() != null) out.addProperty("valueField", safeText(value.valueField()));
                JsonObject variants = new JsonObject();
                for (Map.Entry<String, ? extends Schema<?>> entry : value.variants().entrySet()) {
                    variants.add(safeText(entry.getKey()), visit(entry.getValue(), depth + 1));
                }
                out.add("variants", variants);
            } else if (schema instanceof Schema.Opaque<?> value) {
                out.addProperty("kind", "opaque");
                out.addProperty("fallback", "raw_json");
                if (value.codec() != null) out.addProperty("codecClass", safeText(value.codec().getClass().getName()));
            } else if (schema instanceof Schema.Custom<?> value) {
                out.addProperty("kind", "custom");
                Object widget = value.widgetDef();
                if (widget != null) out.addProperty("widgetClass", safeText(widget.getClass().getName()));
            } else {
                out.addProperty("kind", "unsupported");
                out.addProperty("javaType", safeText(schema.getClass().getName()));
            }

            return out;
        }

        private JsonObject marker(String kind, String reason) {
            JsonObject marker = new JsonObject();
            marker.addProperty("kind", kind);
            marker.addProperty("reason", reason);
            return marker;
        }
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static String enumLabel(Schema.Enum schema, Object value, int index) {
        try {
            String label = (String) schema.label().apply(value);
            return safeText(label == null ? "option-" + index : label);
        } catch (Throwable ignored) {
            return "option-" + index;
        }
    }

    private static void addSafeScalar(JsonObject target, String key, Object value) {
        if (value instanceof String text) {
            target.addProperty(key, safeText(text));
        } else if (value instanceof Boolean bool) {
            target.addProperty(key, bool);
        } else if (value instanceof Number number) {
            double finiteCheck = number.doubleValue();
            if (Double.isFinite(finiteCheck)) target.addProperty(key, number);
        } else if (value != null) {
            target.addProperty(key + "Type", safeText(value.getClass().getName()));
        }
    }

    private static String safeText(String value) {
        if (value == null) return "";
        return value.length() <= 256 ? value : value.substring(0, 256);
    }
}
