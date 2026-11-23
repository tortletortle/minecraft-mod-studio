package com.example;

public final class FakeStreamCodecHelper {
    public void encodeLikeMethod(Object value) {}
}

final class ValueInput { int getIntOr(String key, int fallback) { return fallback; } }
final class ValueOutput { void putInt(String key, int value) {} }
final class SavedDataType<T> {}
final class DeferredRegister<T> {}
final class PacketByteBuf {}
final class RegistryByteBuf {}
final class PayloadTypeRegistry<T> {}
final class PacketCodec<B, V> {}
final class ModConfigSpec {}
final class ForgeConfigSpec {}
final class RegistryBuilder {}
