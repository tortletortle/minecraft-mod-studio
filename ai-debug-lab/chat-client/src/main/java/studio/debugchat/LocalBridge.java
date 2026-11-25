package studio.debugchat;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;

final class LocalBridge {
    private static final int MAX_CONFIG_BYTES = 4096;
    private static final int MAX_RESPONSE_BYTES = 8192;
    private static final int MAX_REQUEST_BYTES = 16384;
    private static final int MAX_CHAT_CHARS = 1600;
    private final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .followRedirects(HttpClient.Redirect.NEVER)
            .proxy(HttpClient.Builder.NO_PROXY)
            .build();

    CompletableFuture<Result> diagnose(Path gameDirectory, JsonObject payload) {
        return CompletableFuture.supplyAsync(() -> readConfig(gameDirectory))
                .thenCompose(config -> {
                    if (config == null) {
                        return CompletableFuture.completedFuture(new Result(false,
                                "请先启动本地诊断桥并生成游戏目录的 config/mms-chat-bridge.json。"));
                    }
                    byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
                    if (body.length > MAX_REQUEST_BYTES) {
                        return CompletableFuture.completedFuture(new Result(false, "诊断请求太长。"));
                    }
                    var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + config.port() + "/v1/diagnose"))
                            .timeout(Duration.ofSeconds(100))
                            .header("Content-Type", "application/json")
                            .header("Authorization", "Bearer " + config.token())
                            .POST(HttpRequest.BodyPublishers.ofByteArray(body))
                            .build();
                    return client.sendAsync(request, HttpResponse.BodyHandlers.limiting(
                                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8), MAX_RESPONSE_BYTES))
                            .handle(LocalBridge::handleResponse);
                });
    }

    private static Config readConfig(Path gameDirectory) {
        Path path = gameDirectory.resolve("config/mms-chat-bridge.json");
        try (var input = Files.newInputStream(path)) {
            byte[] data = input.readNBytes(MAX_CONFIG_BYTES + 1);
            if (data.length > MAX_CONFIG_BYTES) {
                return null;
            }
            var fields = JsonParser.parseString(new String(data, StandardCharsets.UTF_8)).getAsJsonObject();
            var version = fields.getAsJsonPrimitive("version");
            var port = fields.getAsJsonPrimitive("port");
            var token = fields.getAsJsonPrimitive("token");
            if (version == null || port == null || token == null || !version.isNumber() || !port.isNumber()
                    || !token.isString() || !version.getAsString().equals("1") || !port.getAsString().matches("[0-9]{1,5}")) {
                return null;
            }
            int portNumber = port.getAsInt();
            String secret = token.getAsString();
            return portNumber > 0 && portNumber <= 65535 && secret.matches("[A-Za-z0-9_-]{43}")
                    ? new Config(portNumber, secret) : null;
        } catch (IOException | RuntimeException invalid) {
            return null;
        }
    }

    private static Result handleResponse(HttpResponse<String> response, Throwable failure) {
        if (failure instanceof CompletionException && failure.getCause() != null) {
            failure = failure.getCause();
        }
        if (failure instanceof HttpTimeoutException) {
            return new Result(false, "本地诊断超时，请稍后重试。");
        }
        if (failure != null) {
            return new Result(false, "本地诊断桥未响应，请确认服务正在运行。");
        }
        if (response.statusCode() == 401) {
            return new Result(false, "游戏与诊断桥的配对已失效，请重新生成配置。");
        }
        boolean success = response.statusCode() == 200;
        try {
            var fields = JsonParser.parseString(response.body()).getAsJsonObject();
            var text = fields.getAsJsonPrimitive(success ? "reply" : "error");
            if (text != null && text.isString()) {
                String message = text.getAsString().replaceAll("[\\p{Cc}\\p{Cf}§]", " ").strip();
                if (!message.isBlank()) {
                    int length = message.codePointCount(0, message.length());
                    String displayed = length <= MAX_CHAT_CHARS ? message
                            : message.substring(0, message.offsetByCodePoints(0, MAX_CHAT_CHARS)) + "…";
                    return new Result(success, displayed);
                }
            }
        } catch (RuntimeException malformed) {
            // Keep a malformed bridge response out of Minecraft chat.
        }
        return new Result(false, "本地诊断桥返回了无法读取的响应（HTTP " + response.statusCode() + "）。");
    }

    private record Config(int port, String token) {}

    record Result(boolean success, String message) {}
}
