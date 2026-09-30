"""战斗日志聚合：按时间窗口统计每个玩家的输出，事件可能乱序到达且重复上报。

实现要点（口径见 README）：

- 环形时间桶：``window_ms + 1`` 个槽分别对应窗口内每一个毫秒，水位
  ``mark`` 单调向前推进时，被越过的槽整桶回收，每次公共调用摊还 O(1)。
- 事件幂等：``event_id`` 命中即丢弃；id 集合只保留窗口内（及尚未激活）
  的事件，随桶回收一起释放，内存 O(窗口内事件数)。
- 乱序归窗：事件按 ``at_ms`` 落桶，与到达顺序无关；晚到但仍在窗口内的
  事件直接进桶，早于水位的旧事件直接丢弃；晚于水位的事件进最小堆，水位
  到达时激活。
- 查询：每个玩家的窗口伤害总和在入桶/回收时增量维护，``dps`` 与
  ``pending`` 都是 O(1)，不全扫事件表；``scanned`` 只统计惰性推进时
  实际检查过的事件记录（每条事件至多被激活、回收各检查一次）。

查询时刻要求单调不减（战斗日志的墙上时间）。
"""

import heapq

WINDOW_MS = 5000


class CombatLog:
    """战斗日志台账。"""

    def __init__(self, window_ms=WINDOW_MS):
        self.window_ms = window_ms
        self._mark = 0
        size = window_ms + 1
        self._ring = [None] * size
        self._size = size
        self._totals = {}
        self._count = 0
        self._waiting = []
        self._seq = 0
        self._ids = set()
        self.scanned = 0

    def add(self, event_id, player, damage, at_ms):
        """记一条伤害事件；重复 event_id 丢弃，过期事件丢弃。"""
        if event_id in self._ids:
            return
        cutoff = self._mark - self.window_ms
        if at_ms < cutoff:
            return
        self._ids.add(event_id)
        if at_ms <= self._mark:
            self._insert(at_ms, event_id, player, damage)
        else:
            self._seq += 1
            heapq.heappush(
                self._waiting, (at_ms, self._seq, event_id, player, damage)
            )

    def _insert(self, at_ms, event_id, player, damage):
        index = at_ms % self._size
        bucket = self._ring[index]
        record = (player, damage, event_id)
        if bucket is None or bucket[0] != at_ms:
            self._ring[index] = [at_ms, record]
        else:
            bucket.append(record)
        self._totals[player] = self._totals.get(player, 0) + damage
        self._count += 1

    def _advance(self, now_ms):
        if now_ms <= self._mark:
            return
        while self._mark < now_ms:
            self._mark += 1
            index = self._mark % self._size
            bucket = self._ring[index]
            if bucket is not None and bucket[0] == self._mark - self._size:
                records = bucket[1:]
                self.scanned += len(records)
                for player, damage, event_id in records:
                    total = self._totals[player] - damage
                    if total:
                        self._totals[player] = total
                    else:
                        del self._totals[player]
                    self._ids.discard(event_id)
                self._count -= len(records)
                self._ring[index] = None
        cutoff = self._mark - self.window_ms
        while self._waiting and self._waiting[0][0] <= self._mark:
            at_ms, _, event_id, player, damage = heapq.heappop(self._waiting)
            self.scanned += 1
            if at_ms >= cutoff:
                self._insert(at_ms, event_id, player, damage)
            else:
                self._ids.discard(event_id)

    def dps(self, player, now_ms):
        """某个玩家在 [now_ms - window_ms, now_ms] 内的每秒输出。"""
        self._advance(now_ms)
        return self._totals.get(player, 0) * 1000 // self.window_ms

    def pending(self, now_ms):
        """窗口 [now_ms - window_ms, now_ms] 内的去重事件数。"""
        self._advance(now_ms)
        return self._count

    def scanned_count(self):
        return self.scanned
