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
    private static final int MAX_CLASS_ATTRIBUTE_BYTES = 8 * 1024 * 1024;
    private final TinyV2Mappings.Mapping mappings;

    ClassFileSignatureScanner() {
        this(TinyV2Mappings.Mapping.none());
    }

    ClassFileSignatureScanner(TinyV2Mappings.Mapping mappings) {
        this.mappings = mappings;
    }

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
            int[] methodTypeDescriptorIndex = new int[count];
            int[] dynamicNameAndTypeIndex = new int[count];
            int[] tags = new int[count];

            for (int i = 1; i < count; i++) {
                int tag = in.readUnsignedByte();
                tags[i] = tag;
                switch (tag) {
                    case 1 -> utf8[i] = in.readUTF();
                    case 3, 4 -> skipFully(in, 4);
                    case 5, 6 -> { skipFully(in, 8); i++; }
                    case 7 -> classNameIndex[i] = in.readUnsignedShort();
                    case 8, 19, 20 -> skipFully(in, 2);
                    case 16 -> methodTypeDescriptorIndex[i] = in.readUnsignedShort();
                    case 9, 10, 11 -> {
                        memberClassIndex[i] = in.readUnsignedShort();
                        memberNameAndTypeIndex[i] = in.readUnsignedShort();
                    }
                    case 12 -> {
                        nameAndTypeNameIndex[i] = in.readUnsignedShort();
                        nameAndTypeDescriptorIndex[i] = in.readUnsignedShort();
                    }
                    case 15 -> skipFully(in, 3);
                    case 17, 18 -> {
                        skipFully(in, 2); // bootstrap method attribute index
                        dynamicNameAndTypeIndex[i] = in.readUnsignedShort();
                    }
                    default -> throw new IOException("Unknown constant-pool tag " + tag);
                }
            }

            validateReferences(tags, classNameIndex, memberClassIndex, memberNameAndTypeIndex,
                    nameAndTypeNameIndex, nameAndTypeDescriptorIndex, methodTypeDescriptorIndex, dynamicNameAndTypeIndex);

            for (int i = 1; i < count; i++) {
                if (tags[i] == 7) {
                    String className = valueAt(utf8, classNameIndex[i]);
                    if (className != null) {
                        if (className.startsWith("[")) collectDescriptor(className, hits);
                        else collectType(className, hits);
                    }
                } else if (tags[i] == 12) {
                    collectDescriptor(valueAt(utf8, nameAndTypeDescriptorIndex[i]), hits);
                } else if (tags[i] == 16) {
                    collectDescriptor(valueAt(utf8, methodTypeDescriptorIndex[i]), hits);
                } else if (tags[i] == 17 || tags[i] == 18) {
                    int nameAndType = dynamicNameAndTypeIndex[i];
                    collectDescriptor(valueAt(utf8, nameAndTypeDescriptorIndex[nameAndType]), hits);
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
                    if (owner != null && memberName != null) collectMember(owner, memberName, descriptor, hits, "member");
                }
            }

            // Field and method descriptors are not necessarily represented by CONSTANT_Class entries.
            in.readUnsignedShort(); // class access flags
            in.readUnsignedShort(); // this_class
            in.readUnsignedShort(); // super_class
            int interfaceCount = in.readUnsignedShort();
            skipFully(in, interfaceCount * 2L);
            readMembers(in, utf8, hits, false, tags, classNameIndex, memberClassIndex,
                    memberNameAndTypeIndex, nameAndTypeNameIndex, nameAndTypeDescriptorIndex); // fields
            readMembers(in, utf8, hits, true, tags, classNameIndex, memberClassIndex,
                    memberNameAndTypeIndex, nameAndTypeNameIndex, nameAndTypeDescriptorIndex); // methods
            skipAttributes(in); // class attributes
        }
        return hits;
    }

    private static void validateReferences(int[] tags, int[] classNameIndex, int[] memberClassIndex,
                                           int[] memberNameAndTypeIndex, int[] nameAndTypeNameIndex,
                                           int[] nameAndTypeDescriptorIndex, int[] methodTypeDescriptorIndex,
                                           int[] dynamicNameAndTypeIndex) throws IOException {
        for (int i = 1; i < tags.length; i++) {
            if (tags[i] == 7 && !hasTag(tags, classNameIndex[i], 1)) {
                throw new IOException("Invalid CONSTANT_Class name index");
            }
            if ((tags[i] == 9 || tags[i] == 10 || tags[i] == 11)
                    && (!hasTag(tags, memberClassIndex[i], 7) || !hasTag(tags, memberNameAndTypeIndex[i], 12))) {
                throw new IOException("Invalid member reference index");
            }
            if (tags[i] == 12 && (!hasTag(tags, nameAndTypeNameIndex[i], 1)
                    || !hasTag(tags, nameAndTypeDescriptorIndex[i], 1))) {
                throw new IOException("Invalid CONSTANT_NameAndType index");
            }
            if (tags[i] == 16 && !hasTag(tags, methodTypeDescriptorIndex[i], 1)) {
                throw new IOException("Invalid CONSTANT_MethodType descriptor index");
            }
            if ((tags[i] == 17 || tags[i] == 18) && !hasTag(tags, dynamicNameAndTypeIndex[i], 12)) {
                throw new IOException("Invalid dynamic constant name-and-type index");
            }
        }
    }

    private static boolean hasTag(int[] tags, int index, int expectedTag) {
        return index > 0 && index < tags.length && tags[index] == expectedTag;
    }

    private static String classNameAt(String[] utf8, int[] classNameIndex, int classIndex) {
        if (classIndex <= 0 || classIndex >= classNameIndex.length) return null;
        return valueAt(utf8, classNameIndex[classIndex]);
    }

    private static String valueAt(String[] values, int index) {
        return index > 0 && index < values.length ? values[index] : null;
    }

    private void readMembers(DataInputStream in, String[] utf8, Map<String, Set<String>> hits,
                             boolean methods, int[] tags, int[] classNameIndex,
                             int[] memberClassIndex, int[] memberNameAndTypeIndex,
                             int[] nameAndTypeNameIndex, int[] nameAndTypeDescriptorIndex) throws IOException {
        int memberCount = in.readUnsignedShort();
        for (int i = 0; i < memberCount; i++) {
            in.readUnsignedShort(); // access flags
            in.readUnsignedShort(); // name index
            int descriptorIndex = in.readUnsignedShort();
            String descriptor = valueAt(utf8, descriptorIndex);
            if (descriptor != null) collectDescriptor(descriptor, hits);
            if (methods) {
                readMethodAttributes(in, utf8, hits, tags, classNameIndex, memberClassIndex,
                        memberNameAndTypeIndex, nameAndTypeNameIndex, nameAndTypeDescriptorIndex);
            } else skipAttributes(in);
        }
    }

    private void readMethodAttributes(DataInputStream in, String[] utf8, Map<String, Set<String>> hits,
                                      int[] tags, int[] classNameIndex, int[] memberClassIndex,
                                      int[] memberNameAndTypeIndex, int[] nameAndTypeNameIndex,
                                      int[] nameAndTypeDescriptorIndex) throws IOException {
        int attributeCount = in.readUnsignedShort();
        for (int i = 0; i < attributeCount; i++) {
            int nameIndex = in.readUnsignedShort();
            long length = Integer.toUnsignedLong(in.readInt());
            if (length > MAX_CLASS_ATTRIBUTE_BYTES) throw new IOException("Method attribute exceeds class-file limit");
            if ("Code".equals(valueAt(utf8, nameIndex))) {
                byte[] attribute = in.readNBytes((int) length);
                if (attribute.length != (int) length) throw new IOException("Truncated Code attribute");
                scanCodeAttribute(attribute, utf8, hits, tags, classNameIndex, memberClassIndex,
                        memberNameAndTypeIndex, nameAndTypeNameIndex, nameAndTypeDescriptorIndex);
            } else skipFully(in, length);
        }
    }

    private void scanCodeAttribute(byte[] attribute, String[] utf8, Map<String, Set<String>> hits, int[] tags,
                                   int[] classNameIndex, int[] memberClassIndex,
                                   int[] memberNameAndTypeIndex, int[] nameAndTypeNameIndex,
                                   int[] nameAndTypeDescriptorIndex) throws IOException {
        try (DataInputStream codeIn = new DataInputStream(new ByteArrayInputStream(attribute))) {
            codeIn.readUnsignedShort(); // max_stack
            codeIn.readUnsignedShort(); // max_locals
            long codeLength = Integer.toUnsignedLong(codeIn.readInt());
            if (codeLength > MAX_CLASS_BYTES || codeLength > codeIn.available()) {
                throw new IOException("Invalid Code byte length");
            }
            byte[] code = codeIn.readNBytes((int) codeLength);
            scanInstructions(code, utf8, hits, tags, classNameIndex, memberClassIndex,
                    memberNameAndTypeIndex, nameAndTypeNameIndex, nameAndTypeDescriptorIndex);
            int exceptionCount = codeIn.readUnsignedShort();
            skipFully(codeIn, exceptionCount * 8L);
            skipAttributes(codeIn); // Code-level attributes
            if (codeIn.available() != 0) throw new IOException("Trailing bytes in Code attribute");
        }
    }

    private void scanInstructions(byte[] code, String[] utf8, Map<String, Set<String>> hits, int[] tags,
                                   int[] classNameIndex, int[] memberClassIndex,
                                   int[] memberNameAndTypeIndex, int[] nameAndTypeNameIndex,
                                   int[] nameAndTypeDescriptorIndex) throws IOException {
        int pc = 0;
        while (pc < code.length) {
            int opcode = code[pc] & 0xff;
            if (opcode >= 0xb2 && opcode <= 0xb9) {
                requireCodeBytes(code, pc, opcode == 0xb9 ? 5 : 3);
                int cpIndex = unsignedShort(code, pc + 1);
                if (opcode >= 0xb6) resolveCallSite(cpIndex, utf8, hits, tags, classNameIndex, memberClassIndex,
                        memberNameAndTypeIndex, nameAndTypeNameIndex, nameAndTypeDescriptorIndex);
                pc += opcode == 0xb9 ? 5 : 3;
            } else if (opcode == 0xba) {
                requireCodeBytes(code, pc, 5);
                pc += 5; // invokedynamic has no direct owner/name reference
            } else if (opcode == 0xaa) {
                int padding = (4 - ((pc + 1) & 3)) & 3;
                int base = pc + 1 + padding;
                requireCodeBytes(code, pc, 1 + padding + 12);
                int low = signedInt(code, base + 4);
                int high = signedInt(code, base + 8);
                if (high < low) throw new IOException("Invalid tableswitch range");
                long length = 1L + padding + 12L + ((long) high - low + 1L) * 4L;
                if (length > Integer.MAX_VALUE || pc + length > code.length) throw new IOException("Truncated tableswitch");
                pc += (int) length;
            } else if (opcode == 0xab) {
                int padding = (4 - ((pc + 1) & 3)) & 3;
                int base = pc + 1 + padding;
                requireCodeBytes(code, pc, 1 + padding + 8);
                int pairs = signedInt(code, base + 4);
                if (pairs < 0) throw new IOException("Invalid lookupswitch pair count");
                long length = 1L + padding + 8L + (long) pairs * 8L;
                if (length > Integer.MAX_VALUE || pc + length > code.length) throw new IOException("Truncated lookupswitch");
                pc += (int) length;
            } else if (opcode == 0xc4) {
                requireCodeBytes(code, pc, 2);
                int widened = code[pc + 1] & 0xff;
                int length = widened == 0x84 ? 6 : 4;
                requireCodeBytes(code, pc, length);
                pc += length;
            } else {
                int length = fixedInstructionLength(opcode);
                requireCodeBytes(code, pc, length);
                pc += length;
            }
        }
    }

    private void resolveCallSite(int cpIndex, String[] utf8, Map<String, Set<String>> hits, int[] tags,
                                 int[] classNameIndex, int[] memberClassIndex,
                                 int[] memberNameAndTypeIndex, int[] nameAndTypeNameIndex,
                                 int[] nameAndTypeDescriptorIndex) throws IOException {
        if (cpIndex <= 0 || cpIndex >= tags.length) throw new IOException("Invalid bytecode constant-pool index");
        int tag = tags[cpIndex];
        if (tag != 10 && tag != 11) return;
        String owner = classNameAt(utf8, classNameIndex, memberClassIndex[cpIndex]);
        int nameAndType = memberNameAndTypeIndex[cpIndex];
        String name = valueAt(utf8, nameAndTypeNameIndex[nameAndType]);
        String descriptor = valueAt(utf8, nameAndTypeDescriptorIndex[nameAndType]);
        if (owner != null && name != null) collectMember(owner, name, descriptor, hits, "callsite");
    }

    private static int fixedInstructionLength(int opcode) throws IOException {
        if ((opcode >= 0x00 && opcode <= 0x0f) || (opcode >= 0x1a && opcode <= 0x35)
                || (opcode >= 0x3b && opcode <= 0x83) || (opcode >= 0x85 && opcode <= 0x98)
                || (opcode >= 0xac && opcode <= 0xb1) || (opcode >= 0xbe && opcode <= 0xc3)) return 1;
        if (opcode == 0x10 || opcode == 0x12 || (opcode >= 0x15 && opcode <= 0x19) || (opcode >= 0x36 && opcode <= 0x3a)
                || opcode == 0xa9 || opcode == 0xbc) return 2;
        if (opcode == 0x11 || opcode == 0x13 || opcode == 0x14 || opcode == 0x84
                || (opcode >= 0x99 && opcode <= 0xa8) || (opcode >= 0xb2 && opcode <= 0xb8)
                || opcode == 0xbb || opcode == 0xbd || opcode == 0xc0 || opcode == 0xc1
                || opcode == 0xc6 || opcode == 0xc7) return 3;
        if (opcode == 0xc5) return 4;
        if (opcode == 0xc8 || opcode == 0xc9) return 5;
        throw new IOException("Unsupported or reserved bytecode opcode: " + opcode);
    }

    private static void requireCodeBytes(byte[] code, int pc, int length) throws IOException {
        if (length < 1 || pc < 0 || pc + (long) length > code.length) throw new IOException("Truncated bytecode instruction");
    }

    private static int unsignedShort(byte[] code, int at) {
        return ((code[at] & 0xff) << 8) | (code[at + 1] & 0xff);
    }

    private static int signedInt(byte[] code, int at) {
        return ((code[at] & 0xff) << 24) | ((code[at + 1] & 0xff) << 16)
                | ((code[at + 2] & 0xff) << 8) | (code[at + 3] & 0xff);
    }

    private static void skipAttributes(DataInputStream in) throws IOException {
        int count = in.readUnsignedShort();
        for (int i = 0; i < count; i++) {
            in.readUnsignedShort(); // attribute name index
            long length = Integer.toUnsignedLong(in.readInt());
            skipFully(in, length);
        }
    }

    private void collectDescriptor(String descriptor, Map<String, Set<String>> hits) {
        int at = 0;
        while ((at = descriptor.indexOf('L', at)) >= 0) {
            int end = descriptor.indexOf(';', at + 1);
            if (end < 0) return;
            String className = descriptor.substring(at + 1, end);
            collectType(className, hits);
            at = end + 1;
        }
    }

    private void collectType(String className, Map<String, Set<String>> hits) {
        String mappedClassName = mappings.mapClass(className);
        for (Map.Entry<String, List<String>> protocol : TYPE_SIGNATURES.entrySet()) {
            for (String signal : protocol.getValue()) {
                if (matchesType(mappedClassName, signal)) {
                    Set<String> signals = hits.computeIfAbsent(protocol.getKey(), ignored -> new LinkedHashSet<>());
                    signals.add("type:" + signal);
                    if (!mappedClassName.equals(className)) {
                        signals.add("mapped-type:" + className + "->" + mappedClassName);
                    }
                }
            }
        }
    }

    private void collectMember(String owner, String name, String descriptor, Map<String, Set<String>> hits,
                               String evidenceKind) {
        String mappedOwner = mappings.mapClass(owner);
        String member = owner + "#" + name + (descriptor == null ? "" : descriptor);
        String mappedMember = mappedOwner + "#" + name + (descriptor == null ? "" : remapDescriptor(descriptor));
        if ((owner.startsWith("com/mojang/serialization/"))
                && List.of("fieldOf", "optionalFieldOf", "xmap", "flatXmap", "comapFlatMap", "dispatch", "listOf", "unboundedMap").contains(name)) {
            add(hits, "DFU_CODEC", evidenceKind + ":" + member);
        }
        if ((matchesType(mappedOwner, "net/minecraft/network/codec/StreamCodec")
                || matchesType(mappedOwner, "PacketByteBuf") || matchesType(mappedOwner, "PayloadTypeRegistry")
                || matchesType(mappedOwner, "PacketCodec"))
                && List.of("encode", "decode", "encodeStart", "decodeFrom").contains(name)) {
            add(hits, "STREAM_CODEC", evidenceKind + ":" + member);
            if (!mappedOwner.equals(owner)) add(hits, "STREAM_CODEC", "mapped-" + evidenceKind + ":" + mappedMember);
        }
        if ((matchesType(mappedOwner, "net/minecraft/nbt/CompoundTag") || matchesType(mappedOwner, "net/minecraft/nbt/NbtCompound")
                || matchesType(mappedOwner, "ValueInput") || matchesType(mappedOwner, "ValueOutput"))
                && List.of("get", "put", "getInt", "getIntOr", "putInt", "read", "store", "getCompound").contains(name)) {
            add(hits, "NBT_PERSISTENCE", evidenceKind + ":" + member);
            if (!mappedOwner.equals(owner)) add(hits, "NBT_PERSISTENCE", "mapped-" + evidenceKind + ":" + mappedMember);
        }
        if ((matchesType(mappedOwner, "ModConfigSpec") || mappedOwner.startsWith("com/electronwill/nightconfig/")
                || mappedOwner.startsWith("me/shedaniel/autoconfig/") || mappedOwner.startsWith("me/shedaniel/clothconfig/")
                || mappedOwner.startsWith("dev/isxander/yacl/"))
                && List.of("define", "defineInRange", "defineList", "build", "load", "save").contains(name)) {
            add(hits, "CONFIG_FRAMEWORK", evidenceKind + ":" + member);
        }
    }

    private String remapDescriptor(String descriptor) {
        StringBuilder result = new StringBuilder(descriptor.length());
        int at = 0;
        while (at < descriptor.length()) {
            int start = descriptor.indexOf('L', at);
            if (start < 0) {
                result.append(descriptor, at, descriptor.length());
                break;
            }
            int end = descriptor.indexOf(';', start + 1);
            if (end < 0) {
                result.append(descriptor, at, descriptor.length());
                break;
            }
            result.append(descriptor, at, start + 1);
            result.append(mappings.mapClass(descriptor.substring(start + 1, end)));
            result.append(';');
            at = end + 1;
        }
        return result.toString();
    }

    private static boolean matchesType(String className, String signal) {
        if (signal.endsWith("/")) return className.startsWith(signal);
        if (signal.contains("/")) return className.equals(signal) || className.startsWith(signal + "$");
        return className.equals(signal) || className.endsWith("/" + signal)
                || className.contains("/" + signal + "$");
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
                "blue/endless/jankson/", "com/electronwill/nightconfig/", "ModConfigSpec",
                "me/shedaniel/autoconfig/", "me/shedaniel/clothconfig/", "dev/isxander/yacl/",
                "org/tomlj/", "com/moandjiezana/toml/"));
        map.put("ITEM_DATA_COMPONENT", List.of(
                "net/minecraft/core/component/DataComponentType", "net/minecraft/component/DataComponentType"));
        map.put("DATA_ATTACHMENT", List.of(
                "net/fabricmc/fabric/api/attachment/v1/AttachmentType",
                "net/fabricmc/fabric/api/attachment/v1/AttachmentRegistry",
                "net/neoforged/neoforge/attachment/AttachmentType"));
        map.put("SAVED_DATA", List.of("net/minecraft/world/level/saveddata/SavedData", "SavedDataType"));
        map.put("REGISTRY", List.of(
                "net/minecraft/core/Registry", "net/minecraft/resources/ResourceKey",
                "net/minecraft/core/registries/Registries", "DeferredRegister", "RegistryBuilder"));
        return Map.copyOf(map);
    }
}
