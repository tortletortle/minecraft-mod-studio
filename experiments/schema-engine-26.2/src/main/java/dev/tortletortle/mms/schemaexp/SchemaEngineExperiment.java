package dev.tortletortle.mms.schemaexp;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.serialization.Codec;
import com.mojang.serialization.JsonOps;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import net.mehvahdjukaar.codecui.Schema;
import net.mehvahdjukaar.codecui.SchemaCodec;
import net.mehvahdjukaar.codecui.SchemaCodecs;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Optional;

public final class SchemaEngineExperiment implements ClientModInitializer {
    private static final Logger LOGGER = LoggerFactory.getLogger("MMS Schema Engine Experiment");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
    private static final String EXPECTED_CODECUI_VERSION = "26.2-1.4.11";

    @Override
    public void onInitializeClient() {
        JsonObject report = new JsonObject();
        report.addProperty("reportVersion", 1);
        report.addProperty("createdAt", Instant.now().toString());
        report.addProperty("minecraftTarget", "26.2");
        report.addProperty("javaVersion", System.getProperty("java.version"));
        report.addProperty("expectedCodecuiVersion", EXPECTED_CODECUI_VERSION);
        report.addProperty("inferenceMode", SchemaCodecs.inferenceMode().name());

        Optional<String> codecUiVersion = FabricLoader.getInstance()
                .getModContainer("codecui")
                .map(container -> container.getMetadata().getVersion().getFriendlyString());
        report.addProperty("codecuiPresent", codecUiVersion.isPresent());
        report.addProperty("codecuiVersion", codecUiVersion.orElse("missing"));

        JsonArray cases = new JsonArray();
        cases.add(inspect("primitive-int", Codec.INT, JsonParser.parseString("17"), "integer"));
        cases.add(inspect("bounded-list", CodecFixtures.INT_LIST, JsonParser.parseString("[1,2,3]"), "list"));
        cases.add(inspect("string-int-map", CodecFixtures.INT_MAP,
                JsonParser.parseString("{\"iron\":3,\"gold\":5}"), "map"));
        cases.add(inspect("record", CodecFixtures.WEAPON,
                JsonParser.parseString("{\"name\":\"test_blade\",\"damage\":17,\"enabled\":true}"), "record"));
        cases.add(inspect("either", CodecFixtures.TEXT_OR_NUMBER, JsonParser.parseString("\"hello\""), "any_of"));
        report.add("cases", cases);

        int passed = 0;
        for (JsonElement element : cases) {
            if (element.getAsJsonObject().get("passed").getAsBoolean()) passed++;
        }
        report.addProperty("passedCases", passed);
        report.addProperty("totalCases", cases.size());
        boolean overallPass = codecUiVersion.filter(EXPECTED_CODECUI_VERSION::equals).isPresent()
                && passed == cases.size();
        report.addProperty("overallPass", overallPass);

        try {
            Path outputDirectory = FabricLoader.getInstance().getConfigDir().resolve("mms-schema-engine");
            Files.createDirectories(outputDirectory);
            Path output = outputDirectory.resolve("codecui-26.2-smoke.json");
            Files.writeString(output, GSON.toJson(report) + System.lineSeparator(), StandardCharsets.UTF_8);
            LOGGER.info("Schema Engine smoke report written to {} ({} / {} cases passed; overall={})",
                    output, passed, cases.size(), overallPass);
        } catch (Exception exception) {
            LOGGER.error("Could not write Schema Engine smoke report", exception);
        }
    }

    private static <A> JsonObject inspect(String name, Codec<A> codec, JsonElement sample, String expectedKind) {
        JsonObject result = new JsonObject();
        result.addProperty("name", name);
        result.addProperty("codecClass", codec.getClass().getName());
        result.addProperty("expectedKind", expectedKind);

        try {
            Schema<A> schema = SchemaCodec.wrap(codec).schema();
            result.addProperty("actualKind", SchemaProjector.kindOf(schema));
            result.add("projection", new SchemaProjector().project(schema));

            var decoded = codec.parse(JsonOps.INSTANCE, sample);
            result.addProperty("decodeOk", decoded.result().isPresent());
            decoded.error().ifPresent(error -> result.addProperty("decodeError", bounded(error.message())));

            boolean encodeOk = false;
            boolean roundTripEqual = false;
            if (decoded.result().isPresent()) {
                var encoded = codec.encodeStart(JsonOps.INSTANCE, decoded.result().orElseThrow());
                encodeOk = encoded.result().isPresent();
                if (encoded.result().isPresent()) {
                    JsonElement encodedJson = encoded.result().orElseThrow();
                    result.add("encodedJson", encodedJson);
                    roundTripEqual = sample.equals(encodedJson);
                } else {
                    encoded.error().ifPresent(error -> result.addProperty("encodeError", bounded(error.message())));
                }
            }
            result.addProperty("encodeOk", encodeOk);
            result.addProperty("roundTripEqual", roundTripEqual);
            result.addProperty("schemaKindMatches", expectedKind.equals(result.get("actualKind").getAsString()));
            result.addProperty("passed", encodeOk
                    && result.get("decodeOk").getAsBoolean()
                    && roundTripEqual
                    && result.get("schemaKindMatches").getAsBoolean());
        } catch (Throwable throwable) {
            result.addProperty("passed", false);
            result.addProperty("errorType", throwable.getClass().getName());
            result.addProperty("error", bounded(throwable.getMessage()));
            LOGGER.error("Schema probe failed for {}", name, throwable);
        }
        return result;
    }

    private static String bounded(String message) {
        if (message == null) return "unspecified";
        return message.length() <= 512 ? message : message.substring(0, 512);
    }
}
