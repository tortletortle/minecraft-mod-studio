package net.minecraft.network.codec;
public interface StreamCodec<B, V> {
    V decode(B buffer);
    void encode(B buffer, V value);
}
