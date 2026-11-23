package dev.tortletortle.mms.umpd;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Reads only the class-file constant pool. It never defines or executes classes. */
final class ClassFileSignatureScanner {
    private static final Map<String, List<String>> SIGNATURES = signatures();

    Map<String, Set<String>> scan(byte[] classBytes) throws IOException {
        Map<String, Set<String>> hits = new LinkedHashMap<>();
        try (DataInputStream in = new DataInputStream(new ByteArrayInputStream(classBytes))) {
            if (in.readInt() != 0xCAFEBABE) throw new IOException("Invalid class-file magic");
            in.readUnsignedShort(); // minor
            in.readUnsignedShort(); // major
            int count = in.readUnsignedShort();
            for (int i = 1; i < count; i++) {
                int tag = in.readUnsignedByte();
                String text = null;
                switch (tag) {
                    case 1 -> text = in.readUTF();
                    case 3, 4 -> skipFully(in, 4);
                    case 5, 6 -> { skipFully(in, 8); i++; }
                    case 7, 8, 16, 19, 20 -> skipFully(in, 2);
                    case 9, 10, 11, 12, 17, 18 -> skipFully(in, 4);
                    case 15 -> skipFully(in, 3);
                    default -> throw new IOException("Unknown constant-pool tag " + tag);
                }
                if (text != null) collect(text, hits);
            }
        }
        return hits;
    }

    private static void collect(String constant, Map<String, Set<String>> hits) {
        for (Map.Entry<String, List<String>> protocol : SIGNATURES.entrySet()) {
            for (String signal : protocol.getValue()) {
                if (constant.contains(signal)) {
                    hits.computeIfAbsent(protocol.getKey(), ignored -> new LinkedHashSet<>()).add(signal);
                }
            }
        }
    }

    private static void skipFully(DataInputStream in, int bytes) throws IOException {
        int remaining = bytes;
        while (remaining > 0) {
            int skipped = in.skipBytes(remaining);
            if (skipped <= 0) throw new IOException("Unexpected end of constant pool");
            remaining -= skipped;
        }
    }

    private static Map<String, List<String>> signatures() {
        Map<String, List<String>> map = new LinkedHashMap<>();
        map.put("DFU_CODEC", List.of(
                "com/mojang/serialization/Codec", "com/mojang/serialization/MapCodec",
                "com/mojang/serialization/codecs/RecordCodecBuilder", "com/mojang/serialization/DynamicOps",
                "com/mojang/serialization/DataResult"));
        map.put("STREAM_CODEC", List.of(
                "net/minecraft/network/codec/StreamCodec", "net/minecraft/network/protocol/common/custom/CustomPacketPayload",
                "PayloadTypeRegistry", "PacketByteBuf", "RegistryByteBuf", "PacketCodec"));
        map.put("NBT_PERSISTENCE", List.of(
                "net/minecraft/nbt/CompoundTag", "net/minecraft/nbt/NbtCompound", "net/minecraft/nbt/Tag",
                "net/minecraft/nbt/NbtElement", "ValueInput", "ValueOutput", "saveAdditional", "loadAdditional"));
        map.put("JSON_SERIALIZATION", List.of(
                "com/google/gson/Gson", "com/google/gson/JsonParser", "com/fasterxml/jackson/databind/ObjectMapper",
                "org/json/JSONObject"));
        map.put("CONFIG_FRAMEWORK", List.of(
                "blue/endless/jankson", "com/electronwill/nightconfig", "ModConfigSpec",
                "me/shedaniel/autoconfig", "dev/isxander/yacl", "org/tomlj", "com/moandjiezana/toml"));
        map.put("ITEM_DATA_COMPONENT", List.of(
                "net/minecraft/core/component/DataComponentType", "net/minecraft/component/DataComponentType"));
        map.put("DATA_ATTACHMENT", List.of(
                "net/fabricmc/fabric/api/attachment/v1/AttachmentType",
                "net/neoforged/neoforge/attachment/AttachmentType"));
        map.put("SAVED_DATA", List.of("net/minecraft/world/level/saveddata/SavedData", "SavedDataType"));
        map.put("REGISTRY", List.of(
                "net/minecraft/core/Registry", "net/minecraft/resources/ResourceKey",
                "net/minecraft/core/registries/Registries", "DeferredRegister", "RegistryBuilder"));
        return Map.copyOf(map);
    }
}
