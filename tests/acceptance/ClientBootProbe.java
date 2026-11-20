package studio.acceptance;

import java.util.concurrent.atomic.AtomicInteger;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.screen.v1.ScreenEvents;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.client.model.geom.ModelPart;
import studio.generated.m_73746f726d73686172645f6d6f64.StudioMobTypes;
import studio.generated.m_73746f726d73686172645f6d6f64.client.model.StormGuardianEntityModel;
import studio.generated.m_73746f726d73686172645f6d6f64.client.state.StormGuardianRenderState;

/** Test-only client entrypoint. Never included in the release artifact. */
public final class ClientBootProbe implements ClientModInitializer {
    private final AtomicInteger titleFrames = new AtomicInteger();
    private int afterPass;
    private boolean finished;
    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException("MMS_CLIENT_CHECK_FAILED " + message);
    }
    private static void near(float actual, float expected, String label) {
        require(Float.isFinite(actual) && Math.abs(actual - expected) < 0.0001F, label + ": " + actual + " expected " + expected);
    }
    private static Identifier id(String path) {
        return Identifier.fromNamespaceAndPath("stormshard_mod", path);
    }
    @Override public void onInitializeClient() {
        ScreenEvents.AFTER_INIT.register((client, screen, width, height) -> {
            if (screen instanceof TitleScreen) {
                ScreenEvents.afterExtract(screen).register((s, graphics, mx, my, delta) -> titleFrames.incrementAndGet());
            }
        });
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            if (!finished) {
                if (titleFrames.get() < 10) return;
                require(BuiltInRegistries.ENTITY_TYPE.getKey(StudioMobTypes.STORMGUARDIAN).equals(id("storm_guardian")), "entity registry");
                for (String path : new String[]{"stormshard_sword","stormshard_gem","lightning_core","charged_ingot","storm_crystal_ore"}) {
                    require(BuiltInRegistries.ITEM.containsKey(id(path)), "missing item " + path);
                }
                require(BuiltInRegistries.BLOCK.containsKey(id("storm_crystal_ore")), "block registry");
                require(client.getResourceManager().getResource(id("textures/entity/storm_guardian.png")).isPresent(), "entity texture unavailable to resource manager");

                // Invoke actual Minecraft ModelPart and EntityModel code; no world or entity rendering.
                ModelPart baked = StormGuardianEntityModel.createBodyLayer().bakeRoot();
                ModelPart root = baked.getChild("root");
                ModelPart leftLeg = root.getChild("leg_l");
                ModelPart rightArm = root.getChild("body").getChild("arm_r");
                StormGuardianEntityModel model = new StormGuardianEntityModel(baked);
                StormGuardianRenderState state = new StormGuardianRenderState();
                state.walkAnimationSpeed = 1.0F;
                state.ageInTicks = 0F;
                model.setupAnim(state);
                near(leftLeg.xRot, 0.5F, "walk pose tick 0");
                state.ageInTicks = 10F;
                model.setupAnim(state);
                near(leftLeg.xRot, -0.5F, "walk pose tick 10");
                state.studioAnimationId = "attack";
                state.studioAnimationTime = 2;
                model.setupAnim(state);
                near(rightArm.xRot, 1.25F, "attack pose tick 2");
                state.studioAnimationTime = 8;
                model.setupAnim(state);
                near(rightArm.xRot, 0F, "attack pose reset");
                finished = true;
                System.out.println("MMS_CLIENT_PROBE_PASS title_frames=" + titleFrames.get() + " items=5 blocks=1 entities=1 texture=1 poses=4");
            } else if (++afterPass >= 80) {
                client.stop();
            }
        });
    }
}
