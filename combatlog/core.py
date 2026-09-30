"""战斗日志聚合：按时间窗口统计每个玩家的输出，事件可能乱序到达且重复上报。

缺陷：窗口按最后 N 条事件算、重复事件重复累加、乱序事件按到达顺序统计、
窗口外的旧事件从不回收、每次查询全扫所有事件。
"""

WINDOW_MS = 5000


class CombatLog:
    """战斗日志台账。"""

    def __init__(self, window_ms=WINDOW_MS):
        self.window_ms = window_ms
        self.events = []
        self.handled = {}
        self.scanned = 0

    def add(self, event_id, player, damage, at_ms):
        """记一条伤害事件。缺陷：不去重、不按时间窗口裁剪、不按时间排序。"""
        self.events.append((event_id, player, damage, at_ms))

    def dps(self, player, now_ms):
        """某个玩家在当前窗口内的每秒输出。

        缺陷：先看最后十条事件（不是时间窗口），而且每次都全扫事件表。
        """
        self.scanned += len(self.events)
        total = 0
        for _, name, damage, _ in self.events[-10:]:
            if name == player:
                total += damage
        return total * 1000 // self.window_ms

    def pending(self, now_ms):
        """窗口内的事件数。缺陷：过期的旧事件也算在里面。"""
        self.scanned += len(self.events)
        return len(self.events)

    def scanned_count(self):
        return self.scanned
