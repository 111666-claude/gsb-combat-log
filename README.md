# combat-log

战斗日志聚合：按时间窗口统计每个玩家的输出，事件可能乱序到达且重复上报，只用 Python 标准库。

```
python3 -m combatlog.cli --sample window
python3 -m combatlog.cli --sample dup
python3 -m combatlog.cli --sample old
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **窗口按时间**：只统计 `[now - window_ms, now]` 内的事件（含边界），窗口外的必须回收。
- **事件幂等**：同一个 `event_id` 只算一次，重复上报不改变统计结果。
- **乱序按时间归窗**：事件按 `at_ms` 归入窗口，与到达顺序无关。
- **dps 定义**：窗口内该玩家伤害总和乘 1000 整除 `window_ms`。
- **查询代价**：`dps` 与 `pending` 不许每次全扫事件表，`scanned_count()` 不随事件总数线性增长。
- **规模**：单场 200 万条事件、每秒 10 万次查询，单次摊还 O(1)，内存 O(窗口内事件数)。

## 输出契约（不改格式）

```
dps=200
dps=200
pending=0
scanned<=6000
```

## 目录

```
combatlog/core.py   窗口统计与幂等
combatlog/cli.py    命令行入口
tests/              unittest 用例
```
