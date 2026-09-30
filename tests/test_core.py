import random
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


class WindowTest(unittest.TestCase):
    def test_boundary_inclusive(self):
        log = CombatLog(5000)
        log.add("e1", "p", 5000, 1000)
        self.assertEqual(log.dps("p", 6000), 1000)
        self.assertEqual(log.pending(6000), 1)

    def test_outside_window_reclaimed(self):
        log = CombatLog(5000)
        log.add("e1", "p", 5000, 999)
        self.assertEqual(log.dps("p", 6000), 0)
        self.assertEqual(log.pending(6000), 0)

    def test_expired_events_dropped_even_if_added_late(self):
        log = CombatLog(5000)
        log.add("e1", "p", 5000, 10000)
        self.assertEqual(log.pending(10000), 1)
        log.add("e2", "p", 5000, 0)
        self.assertEqual(log.pending(10000), 1)


class IdempotentTest(unittest.TestCase):
    def test_duplicate_event_id_counted_once(self):
        log = CombatLog(5000)
        log.add("e1", "p", 1000, 0)
        log.add("e1", "p", 1000, 10)
        self.assertEqual(log.dps("p", 100), 200)
        self.assertEqual(log.pending(100), 1)

    def test_replay_is_deterministic(self):
        log = CombatLog(5000)
        events = [("e%d" % i, "p", i, i) for i in range(100)]
        for event in events:
            log.add(*event)
        first = (log.dps("p", 200), log.pending(200))
        for event in events:
            log.add(*event)
        self.assertEqual((log.dps("p", 200), log.pending(200)), first)


class OutOfOrderTest(unittest.TestCase):
    def test_late_arrival_counts_by_at_ms(self):
        log = CombatLog(5000)
        log.add("e2", "p", 3000, 6000)
        log.add("e1", "p", 1000, 4000)
        self.assertEqual(log.dps("p", 6000), 800)
        self.assertEqual(log.pending(6000), 2)

    def test_arrival_order_does_not_change_result(self):
        log = CombatLog(5000)
        log.add("e1", "p", 1000, 4000)
        log.add("e2", "p", 3000, 6000)
        self.assertEqual(log.dps("p", 6000), 800)


class QueryCostTest(unittest.TestCase):
    def test_scanned_not_linear_in_event_count(self):
        log = CombatLog(5000)
        for index in range(3000):
            log.add("e-%d" % index, "p", 1, index)
        for _ in range(3000):
            log.pending(3000)
        self.assertLessEqual(log.scanned_count(), 6000)

    def test_scanned_counts_only_reclaimed_buckets(self):
        log = CombatLog(5000)
        for index in range(3000):
            log.add("e-%d" % index, "p", 1, index)
        self.assertEqual(log.pending(100000), 0)
        self.assertLessEqual(log.scanned_count(), 3000)


class DifferentialTest(unittest.TestCase):
    def test_matches_reference_over_random_streams(self):
        for seed in range(200):
            rng = random.Random(seed)
            now = 0
            next_id = 0
            log = CombatLog(5000)
            seen = {}
            for _ in range(rng.randrange(1, 120)):
                if rng.random() < 0.6:
                    if rng.random() < 0.3 and seen:
                        event_id = rng.choice(list(seen))
                        player, damage, at_ms = seen[event_id]
                    else:
                        event_id = "e%d" % next_id
                        next_id += 1
                        player = rng.choice(["p", "q", "r"])
                        damage = rng.randrange(0, 1000)
                        at_ms = rng.randrange(0, now + 1)
                    log.add(event_id, player, damage, at_ms)
                    if event_id not in seen:
                        seen[event_id] = (player, damage, at_ms)
                else:
                    now += rng.randrange(0, 50)
                    player = rng.choice(["p", "q", "r"])
                    lo = now - 5000
                    live = [v for v in seen.values() if lo <= v[2] <= now]
                    expected_dps = (
                        sum(d for n, d, _ in live if n == player) * 1000 // 5000
                    )
                    self.assertEqual(log.dps(player, now), expected_dps)
                    self.assertEqual(log.pending(now), len(live))


if __name__ == "__main__":
    unittest.main()
