package com.mojang.serialization;
public interface Codec<T> {
    Codec<T> fieldOf(String name);
}
