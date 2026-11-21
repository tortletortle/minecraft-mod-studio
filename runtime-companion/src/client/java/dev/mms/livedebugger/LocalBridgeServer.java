package dev.mms.livedebugger;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.EnumSet;
import java.util.HexFormat;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.Minecraft;

/** Authenticated newline-delimited JSON bridge bound exclusively to IPv4 loopback. */
public final class LocalBridgeServer implements AutoCloseable {
    private static final int PROTOCOL_VERSION = 1;
    private static final int MAX_LINE_CHARS = 8192;
    private static final int MAX_OUTSTANDING = 8;
    private static final int MAX_REQUESTS_PER_MINUTE = 120;

    private final PlayerController controller;
    private final AtomicBoolean closed = new AtomicBoolean(false);
    private final AtomicInteger outstanding = new AtomicInteger();
    private final String token = createToken();

    private ServerSocket listener;
    private volatile Socket activeSocket;
    private Thread thread;
    private Path connectionFile;

    public LocalBridgeServer(PlayerController controller) {
        this.controller = controller;
    }

    public void start() throws IOException {
        listener = new ServerSocket();
        listener.setReuseAddress(false);
        listener.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0), 1);
        writeConnectionFile(listener.getLocalPort());

        thread = new Thread(this::acceptLoop, "mms-live-debugger-bridge");
        thread.setDaemon(true);
        thread.start();

        System.out.println("[MMS Live Debugger] READY host=127.0.0.1 port=" + listener.getLocalPort()
                + " connection_file=" + connectionFile);
    }

    private void acceptLoop() {
        while (!closed.get()) {
            try {
                Socket socket = listener.accept();
                if (!socket.getInetAddress().isLoopbackAddress()) {
                    socket.close();
                    continue;
                }
                activeSocket = socket;
                handleConnection(socket);
                activeSocket = null;
            } catch (IOException exception) {
                if (!closed.get()) {
                    System.err.println("[MMS Live Debugger] Connection error: " + exception.getMessage());
                }
            }
        }
    }

    private void handleConnection(Socket socket) {
        try (socket;
             BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
             BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8))) {
            socket.setTcpNoDelay(true);
            String firstLine = readLimitedLine(reader);
            if (firstLine == null) {
                return;
            }

            JsonObject hello;
            try {
                hello = JsonParser.parseString(firstLine).getAsJsonObject();
            } catch (RuntimeException exception) {
                writeLine(writer, errorResponse(null, "INVALID_HANDSHAKE"));
                return;
            }

            String suppliedToken = hello.has("token") && hello.get("token").isJsonPrimitive()
                    ? hello.get("token").getAsString() : "";
            int suppliedProtocol = hello.has("protocol") ? hello.get("protocol").getAsInt() : -1;
            if (suppliedProtocol != PROTOCOL_VERSION || !constantTimeEquals(token, suppliedToken)) {
                writeLine(writer, errorResponse(null, "AUTH_FAILED_OR_PROTOCOL_MISMATCH"));
                return;
            }

            JsonObject accepted = new JsonObject();
            accepted.addProperty("ok", true);
            accepted.addProperty("protocol", PROTOCOL_VERSION);
            JsonArray capabilities = new JsonArray();
            for (String capability : new String[] {
                    "status", "move", "look", "stop", "entities", "inspect_entity", "block"
            }) {
                capabilities.add(capability);
            }
            accepted.add("capabilities", capabilities);
            writeLine(writer, accepted);

            long windowStart = System.nanoTime();
            int requestsInWindow = 0;
            String line;
            while (!closed.get() && (line = readLimitedLine(reader)) != null) {
                long now = System.nanoTime();
                if (now - windowStart >= 60_000_000_000L) {
                    windowStart = now;
                    requestsInWindow = 0;
                }
                requestsInWindow++;
                if (requestsInWindow > MAX_REQUESTS_PER_MINUTE) {
                    writeLine(writer, errorResponse(null, "RATE_LIMITED"));
                    break;
                }

                JsonObject request;
                try {
                    request = JsonParser.parseString(line).getAsJsonObject();
                } catch (RuntimeException exception) {
                    writeLine(writer, errorResponse(null, "INVALID_JSON"));
                    continue;
                }

                if (outstanding.incrementAndGet() > MAX_OUTSTANDING) {
                    outstanding.decrementAndGet();
                    writeLine(writer, errorResponse(request.has("id") ? request.get("id") : null, "TOO_MANY_PENDING_REQUESTS"));
                    continue;
                }

                JsonObject captured = request.deepCopy();
                Minecraft.getInstance().execute(() -> {
                    JsonObject response;
                    try {
                        JsonObject result = controller.execute(Minecraft.getInstance(), captured);
                        response = new JsonObject();
                        response.add("id", captured.has("id") ? captured.get("id").deepCopy() : com.google.gson.JsonNull.INSTANCE);
                        response.addProperty("ok", true);
                        response.add("result", result);
                    } catch (RuntimeException exception) {
                        response = errorResponse(
                                captured.has("id") ? captured.get("id") : null,
                                safeErrorCode(exception));
                    }
                    writeLine(writer, response);
                    outstanding.decrementAndGet();
                });
            }
        } catch (IOException exception) {
            if (!closed.get()) {
                System.err.println("[MMS Live Debugger] Client disconnected: " + exception.getMessage());
            }
        }
    }

    private static String readLimitedLine(BufferedReader reader) throws IOException {
        StringBuilder line = new StringBuilder();
        int value;
        while ((value = reader.read()) != -1) {
            if (value == '\n') {
                if (line.length() > 0 && line.charAt(line.length() - 1) == '\r') {
                    line.setLength(line.length() - 1);
                }
                return line.toString();
            }
            if (line.length() >= MAX_LINE_CHARS) {
                throw new IOException("Protocol line exceeds the configured limit");
            }
            line.append((char) value);
        }
        return line.isEmpty() ? null : line.toString();
    }

    private static void writeLine(BufferedWriter writer, JsonObject value) {
        synchronized (writer) {
            try {
                writer.write(value.toString());
                writer.newLine();
                writer.flush();
            } catch (IOException ignored) {
                // The local agent may disconnect while a client-tick task is queued.
            }
        }
    }

    private static JsonObject errorResponse(com.google.gson.JsonElement id, String code) {
        JsonObject response = new JsonObject();
        response.add("id", id == null ? com.google.gson.JsonNull.INSTANCE : id.deepCopy());
        response.addProperty("ok", false);
        response.addProperty("error", code);
        return response;
    }

    private static String safeErrorCode(RuntimeException exception) {
        String message = exception.getMessage();
        if (message == null || message.isBlank()) {
            return "COMMAND_FAILED";
        }
        return message.replaceAll("[^A-Z0-9_]", "_").toUpperCase();
    }

    private void writeConnectionFile(int port) throws IOException {
        Path directory = FabricLoader.getInstance().getConfigDir().resolve("mms-live-debugger");
        Files.createDirectories(directory);
        connectionFile = directory.resolve("connection.json");
        if (Files.isSymbolicLink(directory) || Files.isSymbolicLink(connectionFile)) {
            throw new IOException("Refusing a symbolic-link connection-file path");
        }

        JsonObject config = new JsonObject();
        config.addProperty("protocol", PROTOCOL_VERSION);
        config.addProperty("host", "127.0.0.1");
        config.addProperty("port", port);
        config.addProperty("token", token);
        config.addProperty("mod_version", "0.1.0");
        Files.writeString(connectionFile, config.toString() + System.lineSeparator(), StandardCharsets.UTF_8);

        try {
            Files.setPosixFilePermissions(connectionFile, EnumSet.of(
                    PosixFilePermission.OWNER_READ,
                    PosixFilePermission.OWNER_WRITE));
        } catch (UnsupportedOperationException ignored) {
            // Windows uses the inherited per-user ACL of the game instance directory.
        }
    }

    private static String createToken() {
        byte[] bytes = new byte[32];
        new SecureRandom().nextBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }

    private static boolean constantTimeEquals(String expected, String supplied) {
        return MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8),
                supplied.getBytes(StandardCharsets.UTF_8));
    }

    @Override
    public void close() {
        if (!closed.compareAndSet(false, true)) {
            return;
        }
        try {
            if (listener != null) {
                listener.close();
            }
        } catch (IOException ignored) {
        }
        try {
            if (activeSocket != null) {
                activeSocket.close();
            }
        } catch (IOException ignored) {
        }
        if (connectionFile != null) {
            try {
                if (Files.exists(connectionFile)
                        && Files.readString(connectionFile, StandardCharsets.UTF_8).contains(token)) {
                    Files.deleteIfExists(connectionFile);
                }
            } catch (IOException ignored) {
            }
        }
    }
}
