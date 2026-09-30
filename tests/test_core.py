import unittest

from combatlog.core import CombatLog


class AddTest(unittest.TestCase):
    def test_add_keeps_event(self):
        log = CombatLog(5000)
        log.add("e1", "p", 100, 0)
        self.assertEqual(log.pending(0), 1)

    def test_scanned_starts_at_zero(self):
        self.assertEqual(CombatLog(5000).scanned_count(), 0)


class DpsTest(unittest.TestCase):
    def test_single_hit_dps(self):
        log = CombatLog(5000)
        log.add("e1", "p", 5000, 0)
        self.assertEqual(log.dps("p", 0), 1000)

    def test_other_player_has_no_dps(self):
        log = CombatLog(5000)
        log.add("e1", "p", 5000, 0)
        self.assertEqual(log.dps("q", 0), 0)


if __name__ == "__main__":
    unittest.main()
