import unittest

from asm_oracle import enrich_mixin_targets


class MixinTargetResolutionTests(unittest.TestCase):
    def test_single_class_annotation_resolves_target(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [{
                "path":"demo/Mixin.class",
                "asm":{
                    "className":"demo/Mixin",
                    "isMixin":True,
                    "mixinTargetClasses":["net/minecraft/world/entity/Entity"]
                }
            }]
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "COMPLETE")
        self.assertEqual(result[0]["targetClasses"], ["net/minecraft/world/entity/Entity"])
        self.assertEqual(result[0]["mixinClassEvidence"][0]["classEntryPath"], "demo/Mixin.class")

    def test_multi_release_variants_are_not_silently_collapsed(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [
                {
                    "path":"demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["a/Target"]}
                },
                {
                    "path":"META-INF/versions/21/demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["b/Target"]}
                }
            ]
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(result[0]["targetClasses"], [])
        self.assertEqual(result[0]["unresolvedMixinClasses"], ["demo.Mixin"])
        self.assertEqual(
            {item["status"] for item in result[0]["mixinClassEvidence"]},
            {"MULTI_RELEASE_VARIANT_AMBIGUOUS"}
        )
        self.assertEqual(len(result[0]["mixinClassEvidence"]), 2)

    def test_unreadable_multi_release_variant_blocks_false_single_variant_resolution(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [
                {
                    "path":"demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["a/Target"]}
                },
                {
                    "path":"META-INF/versions/21/demo/Mixin.class",
                    "asm":{"path":"META-INF/versions/21/demo/Mixin.class","error":"invalid class"}
                }
            ]
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(result[0]["targetClasses"], [])
        self.assertIn(
            "CLASS_VARIANT_PARSE_FAILED",
            {item["status"] for item in result[0]["mixinClassEvidence"]}
        )

    def test_missing_or_non_mixin_class_remains_unresolved(self):
        missing = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Missing"]}], []
        )[0]
        self.assertEqual(missing["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(missing["mixinClassEvidence"][0]["status"], "CLASS_NOT_FOUND_IN_ANALYSIS")

        not_mixin = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.NotMixin"]}],
            [{
                "path":"demo/NotMixin.class",
                "asm":{"className":"demo/NotMixin","isMixin":False,"mixinTargetClasses":[]}
            }]
        )[0]
        self.assertEqual(not_mixin["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(not_mixin["mixinClassEvidence"][0]["status"], "MIXIN_ANNOTATION_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
