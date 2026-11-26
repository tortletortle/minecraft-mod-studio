package studio.acceptance;

import com.example.voidscout.ModEntities;
import com.example.voidscout.VoidScoutEntity;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.GameType;

public final class WorldGameTests {
    @GameTest(maxTicks = 100)
    public void entityRegistrationAttributesAndRightClick(GameTestHelper helper) {
        var mob = helper.spawnMob(ModEntities.VOID_SCOUT, 2, 1, 2)
            .withNoFreeWill()
            .spawn();

        if (mob.getMaxHealth() != 28.0F) {
            throw new AssertionError("Expected max health 28, got " + mob.getMaxHealth());
        }

        Player player = helper.makeMockServerPlayer(GameType.CREATIVE);
        InteractionResult result = UseEntityCallback.EVENT.invoker().interact(
            player, helper.getLevel(), InteractionHand.MAIN_HAND, mob, null
        );

        if (result != InteractionResult.SUCCESS) {
            throw new AssertionError("Right-click callback did not consume the interaction: " + result);
        }
        if (mob.getInteractionCount() != 1) {
            throw new AssertionError("Expected one server-side interaction, got " + mob.getInteractionCount());
        }

        System.out.println("MMS_V01_SERVER_PASS entity_registration_attributes_right_click");
        helper.succeed();
    }
}
