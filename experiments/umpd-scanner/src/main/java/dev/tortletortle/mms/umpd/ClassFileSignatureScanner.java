package dev.tortletortle.mms.umpd;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Reads class/type/member references from the class-file constant pool; never loads classes. */
final class ClassFileSignatureScanner {
    private static final Map<String, List<String>> TYPE_SIGNATURES = typeSignatures();

    Map<String, Set<String>> scan(byte[] classBytes) throws IOException {
        Map<String, Set<String>> hits = new LinkedHashMap<>();
        try (DataInputStream in = new DataInputStream(new ByteArrayInputStream(classBytes))) {
            if (in.readInt() != 0xCAFEBABE) throw new IOException("Invalid class-file magic");
            in.readUnsignedShort(); // minor
            in.readUnsignedShort(); // major
            int count = in.readUnsignedShort();
            String[] utf8 = new String[count];
            int[] classNameIndex = new int[count];
            int[] memberClassIndex = new int[count];
            int[] memberNameAndTypeIndex = new int[count];
            int[] nameAndTypeNameIndex = new int[count];
            int[] nameAndTypeDescriptorIndex = new int[count];
            int[] tags = new int[count];

            for (int i = 1; i < count; i++) {
                int tag = in.readUnsignedByte();
                tags[i] = tag;
                switch (tag) {
                    case 1 -> utf8[i] = in.readUTF();
                    case 3, 4 -> skipFully(in, 4);
                    case 5, 6 -> { skipFully(in, 8); i++; }
                    case 7 -> classNameIndex[i] = in.readUnsignedShort();
                    case 8, 16, 19, 20 -> skipFully(in, 2);
                    case 9, 10, 11 -> {
                        memberClassIndex[i] = in.readUnsignedShort();
                        memberNameAndTypeIndex[i] = in.readUnsignedShort();
                    }
                    case 12 -> {
                        nameAndTypeNameIndex[i] = in.readUnsignedShort();
                        nameAndTypeDescriptorIndex[i] = in.readUnsignedShort();
                    }
                    case 15 -> skipFully(in, 3);
                    case 17, 18 -> skipFully(in, 4);
                    default -> throw new IOException("Unknown constant-pool tag " + tag);
                }
            }

            for (int i = 1; i < count; i++) {
                if (tags[i] == 7) {
                    String className = valueAt(utf8, classNameIndex[i]);
                    if (className != null) collectType(className, hits);
                }
            }
            for (int i = 1; i < count; i++) {
                if (tags[i] == 9 || tags[i] == 10 || tags[i] == 11) {
                    String owner = classNameAt(utf8, classNameIndex, memberClassIndex[i]);
                    int nameAndType = memberNameAndTypeIndex[i];
                    String memberName = valueAt(utf8, nameAndTypeNameIndex[nameAndType]);
                    String descriptor = valueAt(utf8, nameAndTypeDescriptorIndex[nameAndType]);
                    if (owner != null) collectType(owner, hits);
                    if (descriptor != null) collectDescriptor(descriptor, hits);
                    if (owner != null && memberName != null) collectMember(owner, memberName, descriptor, hits);
                }
            }

            // Field and method descriptors are not necessarily represented by CONSTANT_Class entries.
            in.readUnsignedShort(); // class access flags
            in.readUnsignedShort(); // this_class
            in.readUnsignedShort(); // super_class
            int interfaceCount = in.readUnsignedShort();
            skipFully(in, interfaceCount * 2L);
            readMembers(in, utf8, hits); // fields
            readMembers(in, utf8, hits); // methods
            skipAttributes(in); // class attributes
        }
        return hits;
    }

    private static String classNameAt(String[] utf8, int[] classNameIndex, int classIndex) {
        if (classIndex <= 0 || classIndex >= classNameIndex.length) return null;
        return valueAt(utf8, classNameIndex[classIndex]);
    }

    private static String valueAt(String[] values, int index) {
        return index > 0 && index < values.length ? values[index] : null;
    }

    private static void readMembers(DataInputStream in, String[] utf8, Map<String, Set<String>> hits) throws IOException {
        int memberCount = in.readUnsignedShort();
        for (int i = 0; i < memberCount; i++) {
            in.readUnsignedShort(); // access flags
            in.readUnsignedShort(); // name index
            int descriptorIndex = in.readUnsignedShort();
            String descriptor = valueAt(utf8, descriptorIndex);
            if (descriptor != null) collectDescriptor(descriptor, hits);
            skipAttributes(in);
        }
    }

    private static void skipAttributes(DataInputStream in) throws IOException {
        int count = in.readUnsignedShort();
        for (int i = 0; i < count; i++) {
            in.readUnsignedShort(); // attribute name index
            long length = Integer.toUnsignedLong(in.readInt());
            skipFully(in, length);
        }
    }

    private static void collectDescriptor(String descriptor, Map<String, Set<String>> hits) {
        int at = 0;
        while ((at = descriptor.indexOf('L', at)) >= 0) {
            int end = descriptor.indexOf(';', at + 1);
            if (end < 0) return;
            String className = descriptor.substring(at + 1, end);
            collectType(className, hits);
            at = end + 1;
        }
    }

    private static void collectType(String className, Map<String, Set<String>> hits) {
        for (Map.Entry<String, List<String>> protocol : TYPE_SIGNATURES.entrySet()) {
            for (String signal : protocol.getValue()) {
                if (className.contains(signal)) {
                    hits.computeIfAbsent(protocol.getKey(), ignored -> new LinkedHashSet<>()).add("type:" + signal);
                }
            }
        }
    }

    private static void collectMember(String owner, String name, String descriptor, Map<String, Set<String>> hits) {
        String member = owner + "#" + name + (descriptor == null ? "" : descriptor);
        if (owner.contains("com/mojang/serialization/")
                && List.of("fieldOf", "optionalFieldOf", "xmap", "flatXmap", "comapFlatMap", "dispatch", "listOf", "unboundedMap").contains(name)) {
            add(hits, "DFU_CODEC", "member:" + member);
        }
        if ((owner.contains("StreamCodec") || owner.contains("PacketByteBuf") || owner.contains("PayloadTypeRegistry"))
                && List.of("encode", "decode", "encodeStart", "decodeFrom").contains(name)) {
            add(hits, "STREAM_CODEC", "member:" + member);
        }
        if ((owner.contains("CompoundTag") || owner.contains("NbtCompound") || owner.contains("ValueInput") || owner.contains("ValueOutput"))
                && List.of("get", "put", "getIntOr", "putInt", "read", "store", "getCompound").contains(name)) {
            add(hits, "NBT_PERSISTENCE", "member:" + member);
        }
        if ((owner.contains("ModConfigSpec") || owner.contains("nightconfig") || owner.contains("autoconfig") || owner.contains("yacl"))
                && List.of("define", "defineInRange", "defineList", "build", "load", "save").contains(name)) {
            add(hits, "CONFIG_FRAMEWORK", "member:" + member);
        }
    }

    private static void add(Map<String, Set<String>> hits, String protocol, String evidence) {
        hits.computeIfAbsent(protocol, ignored -> new LinkedHashSet<>()).add(evidence);
    }

    private static void skipFully(DataInputStream in, long bytes) throws IOException {
        long remaining = bytes;
        while (remaining > 0) {
            int chunk = (int) Math.min(Integer.MAX_VALUE, remaining);
            int skipped = in.skipBytes(chunk);
            if (skipped <= 0) throw new IOException("Unexpected end of class file");
            remaining -= skipped;
        }
    }

    private static Map<String, List<String>> typeSignatures() {
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
                "net/minecraft/nbt/NbtElement", "ValueInput", "ValueOutput"));
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
