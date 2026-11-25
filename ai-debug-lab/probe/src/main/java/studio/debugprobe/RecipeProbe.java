package studio.debugprobe;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.tags.TagKey;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.CraftingInput;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.ShapedRecipe;
import net.minecraft.world.item.crafting.ShapelessRecipe;
import java.util.ArrayList;
import java.util.List;

/** Explicitly configured targeted lookup; never intentionally mutates world or inventory. */
final class RecipeProbe {
    private static final int MAX_TAG=4096;
    private final Identifier recipe,tag;
    private final String[] inputs;
    private final boolean experiment;
    RecipeProbe(){
        recipe=readId("mms.debug.recipe");tag=readId("mms.debug.item_tag");
        experiment=Boolean.getBoolean("mms.debug.recipe_experiment");
        String raw=System.getProperty("mms.debug.recipe_input","");
        inputs=raw.isEmpty()?new String[0]:raw.split(",",-1);
        if(inputs.length>3)throw new IllegalArgumentException("max three horizontal slots");
        for(String id:inputs)checkedId(id);
        if(experiment && (recipe==null || inputs.length==0))
            throw new IllegalArgumentException("recipe experiment requires recipe and inputs");
    }
    private static Identifier readId(String key){
        String s=System.getProperty(key,"");return s.isEmpty()?null:checkedId(s);
    }
    private static Identifier checkedId(String s){
        if(s.length()>256 || !s.matches("[a-z0-9_.-]+:[a-z0-9_./-]+"))
            throw new IllegalArgumentException("canonical identifier required");
        return Identifier.parse(s);
    }
    boolean configured(){return recipe!=null || tag!=null;}
    JsonObject capture(MinecraftServer server){
        JsonObject out=new JsonObject();
        if(tag!=null){
            JsonObject t=new JsonObject();t.addProperty("id",tag.toString());
            var holders=BuiltInRegistries.ITEM.get(TagKey.create(Registries.ITEM,tag));
            t.addProperty("status",holders.isPresent()?"present":"not_found");
            if(holders.isPresent()){
                var set=holders.get();JsonArray members=new JsonArray();
                set.stream().limit(MAX_TAG).map(h->BuiltInRegistries.ITEM.getKey(h.value()).toString()).sorted().forEach(members::add);
                t.add("members",members);t.addProperty("total",set.size());t.addProperty("complete",set.size()==members.size());
            }
            out.add("item_tag",t);
        }
        if(recipe!=null){
            JsonObject r=new JsonObject();r.addProperty("id",recipe.toString());
            var hit=server.getRecipeManager().byKey(ResourceKey.create(Registries.RECIPE,recipe));
            r.addProperty("status",hit.isPresent()?"present":"not_found");
            if(hit.isPresent()){
                var value=hit.get().value();
                r.addProperty("serializer",BuiltInRegistries.RECIPE_SERIALIZER.getKey(value.getSerializer()).toString());
                if(experiment){
                    JsonObject e=new JsonObject();JsonArray ids=new JsonArray();
                    for(String id:inputs)ids.add(id);
                    e.add("inputs",ids);e.addProperty("scope","in_memory_exact_recipe_only");
                    if(value.getClass()!=ShapedRecipe.class && value.getClass()!=ShapelessRecipe.class){
                        e.addProperty("status","unsupported_implementation");
                    }else{
                        CraftingRecipe crafting=(CraftingRecipe)value;
                        List<ItemStack> stacks=new ArrayList<>();
                        for(String id:inputs){
                            Item item=BuiltInRegistries.ITEM.get(Identifier.parse(id)).orElseThrow().value();
                            stacks.add(new ItemStack(item));
                        }
                        CraftingInput input=CraftingInput.of(stacks.size(),1,stacks);
                        boolean match=crafting.matches(input,server.overworld());
                        e.addProperty("status",match?"matched":"not_matched");
                        if(match){
                            ItemStack result=crafting.assemble(input);
                            e.addProperty("output",BuiltInRegistries.ITEM.getKey(result.getItem()).toString());
                            e.addProperty("count",result.getCount());
                        }
                    }
                    r.add("experiment",e);
                }
            }
            out.add("recipe",r);
        }
        return out;
    }
}
