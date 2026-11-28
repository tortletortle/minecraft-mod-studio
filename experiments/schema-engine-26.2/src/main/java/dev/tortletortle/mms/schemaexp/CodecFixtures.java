package dev.tortletortle.mms.schemaexp;

import com.mojang.datafixers.util.Either;
import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;

import java.util.List;
import java.util.Map;

/**
 * Small, deterministic codecs used to probe the resolver.
 * These are fixtures, not copied or adapted third-party mod code.
 */
public final class CodecFixtures {
    private CodecFixtures() {
    }

    public record Weapon(String name, int damage, boolean enabled) {
    }

    public static final Codec<Weapon> WEAPON = RecordCodecBuilder.create(instance -> instance.group(
            Codec.STRING.fieldOf("name").forGetter(Weapon::name),
            Codec.intRange(0, 64).optionalFieldOf("damage", 12).forGetter(Weapon::damage),
            Codec.BOOL.optionalFieldOf("enabled", true).forGetter(Weapon::enabled)
    ).apply(instance, Weapon::new));

    public static final Codec<List<Integer>> INT_LIST = Codec.intRange(-8, 8).listOf();

    public static final Codec<Map<String, Integer>> INT_MAP =
            Codec.unboundedMap(Codec.STRING, Codec.intRange(0, 64));

    public static final Codec<Either<String, Integer>> TEXT_OR_NUMBER =
            Codec.either(Codec.STRING, Codec.intRange(0, 999));
}
