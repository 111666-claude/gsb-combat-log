"""战斗日志聚合：按时间窗口统计每个玩家的输出，事件可能乱序到达且重复上报。

口径见 README：

- 只统计 ``[now - window_ms, now]``（含边界）内的事件，窗口外的事件立即回收；
- 同一 ``event_id`` 只生效一次，重复上报不改变任何统计；
- 事件按 ``at_ms`` 归窗，与到达顺序无关；
- ``dps`` 为窗口内该玩家伤害总和乘 1000 整除 ``window_ms``。

实现用按 ``at_ms`` 分桶的小顶堆 + 每玩家增量求和：写入与查询都会推进
回收水位，只弹出已过期的桶（每个桶一生只弹出一次），因此
``scanned_count()`` 只与被回收的桶数有关，不随事件总数线性增长；
插入、查询均摊 O(1)，内存只保留窗口内事件。
"""

import heapq

WINDOW_MS = 5000


class CombatLog:
    """战斗日志台账。"""

    def __init__(self, window_ms=WINDOW_MS):
        self.window_ms = window_ms
        # at_ms -> {event_id: (player, damage)}
        self._buckets = {}
        # 非空桶的 at_ms 小顶堆；桶清空即弹出，无脏项。
        self._timeline = []
        self._seen = set()
        self._damage_by_player = {}
        self._size = 0
        # 已回收的 at_ms 上界（小于它的事件按窗口口径属于历史数据）。
        self._evicted_before = None
        # 见过的最大 at_ms，用于在写入路径上同步回收，保证内存只随窗口增长。
        self._max_at_ms = None
        self.scanned = 0

    def add(self, event_id, player, damage, at_ms):
        """记一条伤害事件，按 ``at_ms`` 归入时间窗口。

        重复 ``event_id`` 与已落在窗口外的旧事件都不进入统计。
        """
        if self._evicted_before is not None and at_ms < self._evicted_before:
            return
        if event_id in self._seen:
            return
        self._seen.add(event_id)
        if self._max_at_ms is None or at_ms > self._max_at_ms:
            self._max_at_ms = at_ms
            self._evict(at_ms)
        bucket = self._buckets.get(at_ms)
        if bucket is None:
            bucket = {}
            self._buckets[at_ms] = bucket
            heapq.heappush(self._timeline, at_ms)
        bucket[event_id] = (player, damage)
        self._damage_by_player[player] = self._damage_by_player.get(player, 0) + damage
        self._size += 1

    def _evict(self, now_ms):
        """回收所有 at_ms < now_ms - window_ms 的桶（每个桶只扫一次）。"""
        cutoff = now_ms - self.window_ms
        if self._evicted_before is not None and cutoff <= self._evicted_before:
            return
        self._evicted_before = cutoff
        timeline = self._timeline
        buckets = self._buckets
        damage_by_player = self._damage_by_player
        while timeline and timeline[0] < cutoff:
            at_ms = heapq.heappop(timeline)
            bucket = buckets.pop(at_ms)
            self.scanned += 1
            for event_id in bucket:
                self._seen.discard(event_id)
            for player, damage in bucket.values():
                remaining = damage_by_player[player] - damage
                if remaining:
                    damage_by_player[player] = remaining
                else:
                    del damage_by_player[player]
            self._size -= len(bucket)

    def dps(self, player, now_ms):
        """窗口内该玩家的每秒输出：伤害总和 * 1000 // window_ms。"""
        self._evict(now_ms)
        return self._damage_by_player.get(player, 0) * 1000 // self.window_ms

    def pending(self, now_ms):
        """窗口内的事件数（跨所有玩家）。"""
        self._evict(now_ms)
        return self._size

    def scanned_count(self):
        """查询过程中实际扫描并回收的桶数。"""
        return self.scanned
