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
            ],
            multi_release_enabled=True,
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
            ],
            multi_release_enabled=True,
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


    def test_versioned_entries_are_ignored_without_multi_release_manifest_flag(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [
                {
                    "path":"demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["base/Target"]}
                },
                {
                    "path":"META-INF/versions/21/demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["v21/Target"]}
                }
            ],
            multi_release_enabled=False,
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "COMPLETE")
        self.assertEqual(result[0]["targetClasses"], ["base/Target"])

    def test_multi_release_entries_require_a_pinned_java_view(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [{
                "path":"META-INF/versions/21/demo/Mixin.class",
                "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["v21/Target"]}
            }],
            multi_release_enabled=True,
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(
            result[0]["mixinClassEvidence"][0]["status"],
            "MULTI_RELEASE_RUNTIME_UNPINNED",
        )

    def test_pinned_java_runtime_selects_highest_eligible_multi_release_variant(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [
                {
                    "path":"demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["base/Target"]}
                },
                {
                    "path":"META-INF/versions/11/demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["v11/Target"]}
                },
                {
                    "path":"META-INF/versions/17/demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["v17/Target"]}
                },
                {
                    "path":"META-INF/versions/21/demo/Mixin.class",
                    "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["v21/Target"]}
                },
            ],
            multi_release_enabled=True,
            target_java_version=17,
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "COMPLETE")
        self.assertEqual(result[0]["targetClasses"], ["v17/Target"])
        self.assertEqual(
            result[0]["mixinClassEvidence"][0]["classEntryPath"],
            "META-INF/versions/17/demo/Mixin.class",
        )

    def test_versioned_class_is_unavailable_when_target_runtime_is_too_old(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [{
                "path":"META-INF/versions/21/demo/Mixin.class",
                "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["v21/Target"]}
            }],
            multi_release_enabled=True,
            target_java_version=17,
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(
            result[0]["mixinClassEvidence"][0]["status"],
            "CLASS_NOT_AVAILABLE_FOR_TARGET_RUNTIME",
        )

    def test_class_at_wrong_archive_path_is_not_used_as_mixin_evidence(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [{
                "path":"relocated/Mixin.class",
                "asm":{"className":"demo/Mixin","isMixin":True,"mixinTargetClasses":["wrong/Target"]}
            }],
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(
            result[0]["mixinClassEvidence"][0]["status"],
            "CLASS_ENTRY_PATH_MISMATCH",
        )

    def test_class_name_mismatch_at_expected_path_is_not_accepted(self):
        result = enrich_mixin_targets(
            [{"path":"sample.mixins.json","mixinClasses":["demo.Mixin"]}],
            [{
                "path":"demo/Mixin.class",
                "asm":{"className":"other/Name","isMixin":True,"mixinTargetClasses":["wrong/Target"]}
            }],
        )
        self.assertEqual(result[0]["targetDiscoveryStatus"], "UNRESOLVED")
        self.assertEqual(
            result[0]["mixinClassEvidence"][0]["status"],
            "CLASS_NAME_PATH_MISMATCH",
        )

    def test_rejects_invalid_target_java_version(self):
        for value in (0, -1, True, "21"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    enrich_mixin_targets([], [], target_java_version=value)


if __name__ == "__main__":
    unittest.main()
