package dev.mms.livedebugger;

import java.io.IOException;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.Minecraft;

public final class LiveGameDebuggerClient implements ClientModInitializer {
    private LocalBridgeServer bridge;
    private PlayerController controller;

    @Override
    public void onInitializeClient() {
        controller = new PlayerController();
        ClientTickEvents.END_CLIENT_TICK.register(controller::tick);

        bridge = new LocalBridgeServer(controller);
        try {
            bridge.start();
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to start the local Live Game Debugger bridge", exception);
        }

        ClientLifecycleEvents.CLIENT_STOPPING.register(this::onClientStopping);
    }

    private void onClientStopping(Minecraft client) {
        controller.stop(client);
        if (bridge != null) {
            bridge.close();
        }
    }
}
