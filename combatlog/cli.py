"""命令行入口：跑战斗日志样例。"""

import argparse

from .core import CombatLog


def build_parser():
    parser = argparse.ArgumentParser(prog="combat-log", description="战斗日志聚合")
    parser.add_argument("--sample", default="window", help="window / dup / old / scan")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "window":
        # 六秒前的旧事件与刚刚的新事件。
        log = CombatLog(5000)
        log.add("e1", "p", 3000, 0)
        log.add("e2", "p", 1000, 6000)
        print("dps=%d" % log.dps("p", 6000))
    elif args.sample == "dup":
        log = CombatLog(5000)
        log.add("e1", "p", 1000, 0)
        log.add("e1", "p", 1000, 10)
        print("dps=%d" % log.dps("p", 100))
    elif args.sample == "old":
        log = CombatLog(5000)
        for index in range(3000):
            log.add("e-%d" % index, "p", 1, index)
        print("pending=%d" % log.pending(100000))
    elif args.sample == "scan":
        log = CombatLog(5000)
        for index in range(3000):
            log.add("e-%d" % index, "p", 1, index)
        for _ in range(3000):
            log.pending(3000)
        print("scanned=%d" % log.scanned_count())
    else:
        raise SystemExit("需要 --sample window|dup|old|scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
