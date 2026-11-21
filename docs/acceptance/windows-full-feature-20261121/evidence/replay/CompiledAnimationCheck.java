import java.util.Locale;
import net.minecraft.client.model.geom.ModelPart;
import studio.generated.m_6372797374616c5f6c6162.client.model.StormGuardianEntityModel;
import studio.generated.m_6372797374616c5f6c6162.client.state.StormGuardianRenderState;

public final class CompiledAnimationCheck {
    public static void main(String[] args) {
        ModelPart root = StormGuardianEntityModel.createBodyLayer().bakeRoot();
        StormGuardianEntityModel model = new StormGuardianEntityModel(root);
        ModelPart body = root.getChild("root").getChild("body");
        ModelPart arm = body.getChild("arm_l");
        ModelPart leg = root.getChild("root").getChild("leg_l");
        System.out.printf("{\"model_source\":\"%s\",\"minecraft_source\":\"%s\",\"samples\":[%n",
                StormGuardianEntityModel.class.getProtectionDomain().getCodeSource().getLocation(),
                ModelPart.class.getProtectionDomain().getCodeSource().getLocation());
        sample(model, leg, arm, "", 0, false);
        sample(model, leg, arm, "walk", 10, false);
        sample(model, leg, arm, "attack", 2, true);
        System.out.println("]}");
    }

    private static void sample(StormGuardianEntityModel model, ModelPart leg, ModelPart arm,
            String id, double stateTick, boolean last) {
        StormGuardianRenderState state = new StormGuardianRenderState();
        state.ageInTicks = 0;
        state.walkAnimationSpeed = 0.6F;
        state.studioAnimationId = id;
        state.studioAnimationTime = stateTick;
        model.setupAnim(state);
        System.out.printf(Locale.ROOT,
                "{\"state_clip\":\"%s\",\"state_tick\":%.1f,\"age_in_ticks\":%.1f,\"left_leg_x_rotation\":%.6f,\"left_arm_x_rotation\":%.6f}%s%n",
                id, stateTick, state.ageInTicks, leg.xRot, arm.xRot, last ? "" : ",");
    }
}
