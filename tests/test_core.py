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
    def test_old_event_is_reclaimed(self):
        log = CombatLog(5000)
        log.add("e1", "p", 3000, 0)
        log.add("e2", "p", 1000, 6000)
        self.assertEqual(log.dps("p", 6000), 200)
        self.assertEqual(log.pending(6000), 1)

    def test_boundaries_are_inclusive(self):
        log = CombatLog(5000)
        log.add("lo", "p", 1000, 0)
        log.add("hi", "p", 1000, 5000)
        self.assertEqual(log.pending(5000), 2)
        self.assertEqual(log.dps("p", 5000), 400)
        self.assertEqual(log.pending(5001), 1)
        self.assertEqual(log.dps("p", 5001), 200)

    def test_pending_far_future_is_zero(self):
        log = CombatLog(5000)
        for index in range(3000):
            log.add("e-%d" % index, "p", 1, index)
        self.assertEqual(log.pending(100000), 0)

    def test_late_arrival_within_window_counts(self):
        log = CombatLog(5000)
        log.add("new", "p", 1000, 4000)
        log.add("late", "p", 1000, 1000)
        self.assertEqual(log.pending(4000), 2)
        self.assertEqual(log.dps("p", 4000), 400)

    def test_late_arrival_outside_window_dropped(self):
        log = CombatLog(5000)
        log.add("new", "p", 1000, 6000)
        log.add("late", "p", 9999, 0)
        self.assertEqual(log.pending(6000), 1)
        self.assertEqual(log.dps("p", 6000), 200)


class IdempotenceTest(unittest.TestCase):
    def test_duplicate_event_counts_once(self):
        log = CombatLog(5000)
        log.add("e1", "p", 1000, 0)
        log.add("e1", "p", 1000, 10)
        self.assertEqual(log.pending(100), 1)
        self.assertEqual(log.dps("p", 100), 200)

    def test_duplicate_with_different_payload_ignored(self):
        log = CombatLog(5000)
        log.add("e1", "p", 1000, 0)
        log.add("e1", "p", 9999, 10)
        self.assertEqual(log.dps("p", 100), 200)

    def test_repeated_queries_are_stable(self):
        log = CombatLog(5000)
        log.add("e1", "p", 1000, 0)
        log.add("e1", "p", 1000, 10)
        first = [log.dps("p", 100), log.pending(100)]
        for _ in range(100):
            self.assertEqual([log.dps("p", 100), log.pending(100)], first)


class OutOfOrderTest(unittest.TestCase):
    def test_order_of_arrival_does_not_matter(self):
        forward = CombatLog(5000)
        for at_ms in range(0, 5000, 500):
            forward.add("f%d" % at_ms, "p", 500, at_ms)
        shuffled = CombatLog(5000)
        timestamps = list(range(0, 5000, 500))
        random.Random(42).shuffle(timestamps)
        for at_ms in timestamps:
            shuffled.add("f%d" % at_ms, "p", 500, at_ms)
        for now_ms in (0, 2500, 4999, 5000, 7000):
            self.assertEqual(
                shuffled.pending(now_ms), forward.pending(now_ms), now_ms
            )
            self.assertEqual(
                shuffled.dps("p", now_ms), forward.dps("p", now_ms), now_ms
            )

    def test_future_event_activates_at_its_timestamp(self):
        log = CombatLog(5000)
        log.add("future", "p", 5000, 3000)
        self.assertEqual(log.pending(0), 0)
        self.assertEqual(log.dps("p", 0), 0)
        self.assertEqual(log.pending(3000), 1)
        self.assertEqual(log.dps("p", 3000), 1000)


class ScanCostTest(unittest.TestCase):
    def _drive(self, num_events):
        log = CombatLog(5000)
        for index in range(num_events):
            log.add("e-%d" % index, "p", 1, index)
        log.pending(3000)
        first = log.scanned_count()
        for _ in range(2999):
            log.pending(3000)
        return first, log.scanned_count()

    def test_repeated_queries_do_not_rescan(self):
        first, after_3000 = self._drive(3000)
        self.assertLessEqual(after_3000, 6000)
        self.assertEqual(first, after_3000)

    def test_scanned_does_not_grow_with_event_count(self):
        _, small = self._drive(1000)
        _, large = self._drive(4000)
        self.assertLessEqual(large, 6000)
        self.assertLessEqual(large - small, 6000)


class ReferenceLog:
    """朴素参考实现：每次查询按时间窗口归集 + event_id 幂等去重。"""

    def __init__(self, window_ms):
        self.window_ms = window_ms
        self.mark = 0
        self.active = {}
        self.waiting = []
        self.known = set()

    def add(self, event_id, player, damage, at_ms):
        if event_id in self.known:
            return
        if at_ms < self.mark - self.window_ms:
            return
        self.known.add(event_id)
        if at_ms <= self.mark:
            self.active[event_id] = (player, damage, at_ms)
        else:
            self.waiting.append((at_ms, event_id, player, damage))

    def advance(self, now_ms):
        while self.mark < now_ms:
            self.mark += 1
            cutoff = self.mark - self.window_ms
            expired = [
                event_id
                for event_id, (_, _, at_ms) in self.active.items()
                if at_ms < cutoff
            ]
            for event_id in expired:
                del self.active[event_id]
                self.known.discard(event_id)
            promoted = [item for item in self.waiting if item[0] == self.mark]
            self.waiting = [item for item in self.waiting if item[0] != self.mark]
            for at_ms, event_id, player, damage in promoted:
                if at_ms >= cutoff:
                    self.active[event_id] = (player, damage, at_ms)
                else:
                    self.known.discard(event_id)
        cutoff = self.mark - self.window_ms
        stale = [item for item in self.waiting if item[0] < cutoff]
        for item in stale:
            self.waiting.remove(item)
            self.known.discard(item[1])

    def dps(self, player, now_ms):
        self.advance(now_ms)
        total = sum(
            damage
            for name, damage, _ in self.active.values()
            if name == player
        )
        return total * 1000 // self.window_ms

    def pending(self, now_ms):
        self.advance(now_ms)
        return len(self.active)


class ReferenceComparisonTest(unittest.TestCase):
    def test_random_streams_match_reference(self):
        rng = random.Random(20261001)
        for case in range(200):
            window_ms = rng.choice((100, 500, 1000, 5000))
            real = CombatLog(window_ms)
            ref = ReferenceLog(window_ms)
            mark = 0
            catalog = []
            players = ["p", "q", "r"]
            for _ in range(rng.randint(50, 300)):
                kind = rng.random()
                if kind < 0.7 or not catalog:
                    event_id = "id-%d" % len(catalog)
                    player = rng.choice(players)
                    damage = rng.randint(1, 2000)
                    at_ms = max(0, mark + rng.randint(-2 * window_ms, window_ms))
                    catalog.append((event_id, player, damage, at_ms))
                    real.add(event_id, player, damage, at_ms)
                    ref.add(event_id, player, damage, at_ms)
                elif kind < 0.85:
                    event_id, player, damage, at_ms = rng.choice(catalog)
                    real.add(event_id, player, damage, at_ms)
                    ref.add(event_id, player, damage, at_ms)
                else:
                    event_id, _, _, _ = rng.choice(catalog)
                    player = rng.choice(players)
                    damage = rng.randint(1, 2000)
                    at_ms = max(0, mark + rng.randint(-window_ms, window_ms // 2))
                    real.add(event_id, player, damage, at_ms)
                    ref.add(event_id, player, damage, at_ms)
                if rng.random() < 0.5:
                    mark += rng.randint(0, window_ms // 2)
                    player = rng.choice(players)
                    self.assertEqual(
                        real.pending(mark), ref.pending(mark), (case, mark)
                    )
                    self.assertEqual(
                        real.dps(player, mark),
                        ref.dps(player, mark),
                        (case, player, mark),
                    )
            for player in players:
                self.assertEqual(
                    real.dps(player, mark), ref.dps(player, mark), (case, player)
                )
            self.assertEqual(real.pending(mark), ref.pending(mark), case)


if __name__ == "__main__":
    unittest.main()
