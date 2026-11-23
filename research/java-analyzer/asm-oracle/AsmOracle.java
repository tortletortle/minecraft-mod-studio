import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.Handle;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.Type;

/**
 * Read-only ASM oracle. Class bytes arrive over stdin; no class is defined,
 * initialized, loaded through a class loader, or executed.
 */
public final class AsmOracle {
    private static final int MAX_CLASS_BYTES = 16 * 1024 * 1024;
    private static final int MAX_PATH_BYTES = 4096;
    private static final int MAX_INVOCATION_SAMPLES = 500;
    private static final String MIXIN_DESC = "Lorg/spongepowered/asm/mixin/Mixin;";

    private static final class MethodInfo {
        final String name;
        final String descriptor;
        final int access;

        MethodInfo(String name, String descriptor, int access) {
            this.name = name;
            this.descriptor = descriptor;
            this.access = access;
        }

        String toJson() {
            return "{\"name\":" + quote(name) + ",\"descriptor\":" + quote(descriptor)
                    + ",\"access\":" + access + "}";
        }
    }

    private static final class Invocation {
        final String callerMethod;
        final String callerDescriptor;
        final String opcode;
        final String owner;
        final String name;
        final String descriptor;
        final boolean isInterface;

        Invocation(String callerMethod, String callerDescriptor, int opcode,
                   String owner, String name, String descriptor, boolean isInterface) {
            this.callerMethod = callerMethod;
            this.callerDescriptor = callerDescriptor;
            this.opcode = opcodeName(opcode);
            this.owner = owner;
            this.name = name;
            this.descriptor = descriptor;
            this.isInterface = isInterface;
        }

        String toJson() {
            return "{\"callerMethod\":" + quote(callerMethod)
                    + ",\"callerDescriptor\":" + quote(callerDescriptor)
                    + ",\"opcode\":" + quote(opcode)
                    + ",\"owner\":" + quote(owner)
                    + ",\"name\":" + quote(name)
                    + ",\"descriptor\":" + quote(descriptor)
                    + ",\"isInterface\":" + isInterface + "}";
        }
    }

    private static final class Collector extends ClassVisitor {
        String name;
        String superName;
        int version;
        int access;
        int fieldCount;
        final List<String> interfaces = new ArrayList<>();
        final List<MethodInfo> methods = new ArrayList<>();
        final List<Invocation> invocations = new ArrayList<>();
        final List<String> mixinTargetClasses = new ArrayList<>();
        int invocationCount;
        int invokedynamicCount;
        boolean isMixin;

        Collector() {
            super(Opcodes.ASM9);
        }

        @Override
        public void visit(int version, int access, String name, String signature,
                          String superName, String[] interfaces) {
            this.version = version;
            this.access = access;
            this.name = name;
            this.superName = superName;
            if (interfaces != null) {
                for (String value : interfaces) this.interfaces.add(value);
            }
        }

        @Override
        public void visitOuterClass(String owner, String name, String descriptor) {
            // Deliberately not resolving enclosing classes or loading symbols.
        }

        @Override
        public org.objectweb.asm.FieldVisitor visitField(int access, String name,
                String descriptor, String signature, Object value) {
            fieldCount++;
            return null;
        }

        @Override
        public AnnotationVisitor visitAnnotation(String descriptor, boolean visible) {
            if (!MIXIN_DESC.equals(descriptor)) return null;
            isMixin = true;
            return new AnnotationVisitor(Opcodes.ASM9) {
                private void collect(String elementName, Object value) {
                    if ("value".equals(elementName) && value instanceof Type) {
                        Type type = (Type) value;
                        if (type.getSort() == Type.OBJECT) mixinTargetClasses.add(type.getInternalName());
                    } else if ("targets".equals(elementName) && value instanceof String) {
                        mixinTargetClasses.add(normalizeTarget((String) value));
                    }
                }

                @Override
                public void visit(String name, Object value) {
                    collect(name, value);
                }

                @Override
                public AnnotationVisitor visitArray(final String name) {
                    return new AnnotationVisitor(Opcodes.ASM9) {
                        @Override
                        public void visit(String ignored, Object value) {
                            collect(name, value);
                        }
                    };
                }
            };
        }

        @Override
        public MethodVisitor visitMethod(int access, final String name,
                final String descriptor, String signature, String[] exceptions) {
            methods.add(new MethodInfo(name, descriptor, access));
            return new MethodVisitor(Opcodes.ASM9) {
                @Override
                public void visitMethodInsn(int opcode, String owner, String methodName,
                        String methodDescriptor, boolean isInterface) {
                    invocationCount++;
                    if (invocations.size() < MAX_INVOCATION_SAMPLES) {
                        invocations.add(new Invocation(name, descriptor, opcode, owner,
                                methodName, methodDescriptor, isInterface));
                    }
                }

                @Override
                public void visitInvokeDynamicInsn(String dynamicName, String dynamicDescriptor,
                        Handle bootstrapMethodHandle, Object... bootstrapMethodArguments) {
                    invokedynamicCount++;
                }
            };
        }

        String toJson(String path) {
            StringBuilder out = new StringBuilder(2048);
            out.append("{\"path\":").append(quote(path));
            out.append(",\"className\":").append(quote(name));
            out.append(",\"majorVersion\":").append(version & 0xFFFF);
            out.append(",\"minorVersion\":").append((version >>> 16) & 0xFFFF);
            out.append(",\"access\":").append(access);
            out.append(",\"superName\":").append(nullableQuote(superName));
            out.append(",\"interfaces\":").append(stringArray(interfaces));
            out.append(",\"fieldCount\":").append(fieldCount);
            out.append(",\"methods\":[");
            for (int i = 0; i < methods.size(); i++) {
                if (i > 0) out.append(',');
                out.append(methods.get(i).toJson());
            }
            out.append("],\"invocations\":[");
            for (int i = 0; i < invocations.size(); i++) {
                if (i > 0) out.append(',');
                out.append(invocations.get(i).toJson());
            }
            out.append("],\"invocationCount\":").append(invocationCount);
            out.append(",\"invocationsTruncated\":")
                    .append(invocationCount > invocations.size());
            out.append(",\"invokedynamicCount\":").append(invokedynamicCount);
            out.append(",\"isMixin\":").append(isMixin);
            out.append(",\"mixinTargetClasses\":")
                    .append(stringArray(uniqueSorted(mixinTargetClasses)));
            out.append('}');
            return out.toString();
        }
    }

    private static String normalizeTarget(String value) {
        return value.replace('.', '/');
    }

    private static List<String> uniqueSorted(List<String> values) {
        java.util.TreeSet<String> sorted = new java.util.TreeSet<>(values);
        return new ArrayList<>(sorted);
    }

    private static String opcodeName(int opcode) {
        switch (opcode) {
            case Opcodes.INVOKEVIRTUAL: return "invokevirtual";
            case Opcodes.INVOKESPECIAL: return "invokespecial";
            case Opcodes.INVOKESTATIC: return "invokestatic";
            case Opcodes.INVOKEINTERFACE: return "invokeinterface";
            default: return "opcode_" + opcode;
        }
    }

    private static String nullableQuote(String value) {
        return value == null ? "null" : quote(value);
    }

    private static String stringArray(List<String> values) {
        StringBuilder out = new StringBuilder("[");
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) out.append(',');
            out.append(quote(values.get(i)));
        }
        return out.append(']').toString();
    }

    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\b': out.append("\\b"); break;
                case '\f': out.append("\\f"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
            }
        }
        return out.append('"').toString();
    }

    private static String errorJson(String path, String message) {
        return "{\"path\":" + quote(path) + ",\"error\":" + quote(message) + "}";
    }

    public static void main(String[] args) throws IOException {
        DataInputStream input = new DataInputStream(new BufferedInputStream(System.in));
        while (true) {
            final int pathLength;
            try {
                pathLength = input.readUnsignedShort();
            } catch (EOFException end) {
                return;
            }
            if (pathLength < 1 || pathLength > MAX_PATH_BYTES) {
                throw new IOException("invalid framed path length");
            }
            byte[] pathBytes = new byte[pathLength];
            input.readFully(pathBytes);
            String path = new String(pathBytes, StandardCharsets.UTF_8);
            int classLength = input.readInt();
            if (classLength < 1 || classLength > MAX_CLASS_BYTES) {
                System.out.println(errorJson(path, "class entry exceeds oracle size limit"));
                continue;
            }
            byte[] classBytes = new byte[classLength];
            input.readFully(classBytes);
            try {
                Collector collector = new Collector();
                new ClassReader(classBytes).accept(
                        collector, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
                System.out.println(collector.toJson(path));
            } catch (RuntimeException failure) {
                System.out.println(errorJson(path,
                        failure.getClass().getSimpleName() + ": " + String.valueOf(failure.getMessage())));
            }
        }
    }
}
