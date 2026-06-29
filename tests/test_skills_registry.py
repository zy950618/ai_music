from __future__ import annotations

import unittest

from music_ai.skills import CORE_GATE_SKILL_IDS, agent_names, foundation_skill_ids, get_rework_rule, skills_snapshot


class SkillsRegistryTest(unittest.TestCase):
    def test_core_gate_skills_are_registered(self) -> None:
        registered = foundation_skill_ids()
        for skill_id in CORE_GATE_SKILL_IDS:
            self.assertIn(skill_id, registered)

    def test_agent_registry_contains_full_production_chain(self) -> None:
        names = agent_names()
        self.assertIn("Daily Production Planner", names)
        self.assertIn("Generation Router", names)
        self.assertIn("Music Quality Judge", names)
        self.assertIn("Rights Configurator", names)
        self.assertIn("Delivery Packager", names)
        self.assertEqual(len(names), 26)

    def test_rework_rules_distinguish_music_rework_from_delivery_block(self) -> None:
        duration_rule = get_rework_rule("STRUCTURE_TOO_SHORT")
        self.assertIsNotNone(duration_rule)
        self.assertEqual(duration_rule.target_agent, "Brief Parser")
        self.assertTrue(duration_rule.auto_rework_allowed)

        rights_rule = get_rework_rule("RIGHTS_MISSING")
        self.assertIsNotNone(rights_rule)
        self.assertTrue(rights_rule.delivery_block_only)
        self.assertFalse(rights_rule.auto_rework_allowed)

        hook_rule = get_rework_rule("WEAK_HOOK")
        self.assertIsNotNone(hook_rule)
        self.assertEqual(hook_rule.target_agent, "Melody Composer")

    def test_skills_snapshot_is_api_ready(self) -> None:
        snapshot = skills_snapshot()
        self.assertEqual(len(snapshot["foundation_skills"]), 17)
        self.assertEqual(len(snapshot["agents"]), 26)
        self.assertIn("rework_rules", snapshot)


if __name__ == "__main__":
    unittest.main()
