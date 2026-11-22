"""Разбор логов для поддержки L2: от жалобы клиента к причине в логах.

Команды:
  python triage.py errors              # всплески 5xx — массовый ли сбой
  python triage.py slow                # у каких клиентов сервис отвечает медленно
  python triage.py bruteforce          # подбор пароля: IP с серией неудачных входов
  python triage.py user u0215          # все запросы клиента + ошибки приложения по ним
  python triage.py trace req-006078    # один запрос насквозь: nginx -> приложение
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LOGS = Path(__file__).parent / "logs"
ACCESS_RE = re.compile(
    r'^(?P<ip>\S+) - - \[(?P<ts>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) [^"]+" '
    r'(?P<status>\d{3}) \d+ "[^"]*" "[^"]*" rt=(?P<rt>[\d.]+) rid=(?P<rid>\S+)$')
AUTH_RE = re.compile(r"^(?P<ts>\S+) login (?P<result>\w+) user=(?P<user>\S+) ip=(?P<ip>\S+)$")


def read_access(logs=LOGS):
    rows = []
    for line in (logs / "access.log").read_text(encoding="utf-8").splitlines():
        m = ACCESS_RE.match(line)
        if not m:
            continue
        d = m.groupdict()
        d["ts"] = datetime.strptime(d["ts"], "%d/%b/%Y:%H:%M:%S %z").replace(tzinfo=None)
        d["status"] = int(d["status"])
        d["ms"] = round(float(d.pop("rt")) * 1000)
        rows.append(d)
    return rows


def read_app(logs=LOGS):
    return [json.loads(line) for line in (logs / "app.log").read_text(encoding="utf-8").splitlines() if line]


def read_auth(logs=LOGS):
    rows = []
    for line in (logs / "auth.log").read_text(encoding="utf-8").splitlines():
        m = AUTH_RE.match(line)
        if m:
            d = m.groupdict()
            d["ts"] = datetime.fromisoformat(d["ts"])
            rows.append(d)
    return rows


def error_bursts(access, gap=timedelta(minutes=5), min_errors=5):
    """Всплески 5xx: ошибки одного эндпоинта, идущие с разрывом не больше gap.
    Единичная ошибка — это тикет одного клиента, всплеск — инцидент для дежурного."""
    by_ep = defaultdict(list)
    for r in access:
        if r["status"] >= 500:
            by_ep[(r["method"], r["path"])].append(r)
    result = []
    for (method, path), rows in by_ep.items():
        rows.sort(key=lambda r: r["ts"])
        burst = [rows[0]]
        for r in rows[1:] + [None]:
            if r is not None and r["ts"] - burst[-1]["ts"] <= gap:
                burst.append(r)
                continue
            if len(burst) >= min_errors:
                result.append({
                    "endpoint": f"{method} {path}",
                    "errors": len(burst),
                    "from": burst[0]["ts"].strftime("%H:%M:%S"),
                    "to": burst[-1]["ts"].strftime("%H:%M:%S"),
                    "statuses": dict(Counter(x["status"] for x in burst)),
                    "avg_ms": round(sum(x["ms"] for x in burst) / len(burst)),
                })
            if r is not None:
                burst = [r]
    return sorted(result, key=lambda x: -x["errors"])


def percentile(values, p):
    values = sorted(values)
    k = max(0, round(p / 100 * len(values)) - 1)
    return values[k]


def slow_for_users(access, app, threshold_ms=1000, min_requests=2):
    """Кому сервис отвечает медленно: медиана времени ответа по паре (эндпоинт, пользователь).
    Общий p95 может быть нормальным, а у отдельных клиентов страница «висит»."""
    user_by_rid = {e["request_id"]: e["user"] for e in app if e["level"] == "INFO"}
    times = defaultdict(list)
    for r in access:
        if r["status"] < 500:
            times[(f'{r["method"]} {r["path"]}', user_by_rid.get(r["rid"]))].append(r["ms"])
    result = []
    for (endpoint, user), ms in times.items():
        if len(ms) >= min_requests and percentile(ms, 50) >= threshold_ms:
            all_ms = [x for (ep, _), xs in times.items() if ep == endpoint for x in xs]
            result.append({"endpoint": endpoint, "user": user, "requests": len(ms),
                           "median_ms": percentile(ms, 50), "endpoint_p95_ms": percentile(all_ms, 95)})
    return sorted(result, key=lambda x: -x["median_ms"])


def bruteforce(auth, window=timedelta(minutes=10), min_failures=10):
    """IP, с которых за окно было >= min_failures неудачных входов."""
    fails = defaultdict(list)
    for r in auth:
        if r["result"] == "failure":
            fails[r["ip"]].append(r)
    result = []
    for ip, rows in fails.items():
        rows.sort(key=lambda r: r["ts"])
        best, start = 0, 0
        for end in range(len(rows)):
            while rows[end]["ts"] - rows[start]["ts"] > window:
                start += 1
            best = max(best, end - start + 1)
        if best >= min_failures:
            result.append({"ip": ip, "failures": len(rows), "max_in_window": best,
                           "users": sorted({r["user"] for r in rows}),
                           "first": rows[0]["ts"], "last": rows[-1]["ts"]})
    return result


def user_activity(app, user):
    """Все проблемные события клиента: ошибки, предупреждения и неуспешные ответы."""
    return [e for e in app if e["user"] == user and (e["level"] != "INFO" or e.get("status", 200) >= 400)]


def trace(access, app, rid):
    return {"access": [r for r in access if r["rid"] == rid],
            "app": [e for e in app if e["request_id"] == rid]}


def _print_rows(rows):
    for r in rows:
        print("  " + "  ".join(f"{k}={v}" for k, v in r.items()))
    if not rows:
        print("  ничего не найдено")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("errors")
    sub.add_parser("slow")
    sub.add_parser("bruteforce")
    sub.add_parser("user").add_argument("user")
    sub.add_parser("trace").add_argument("rid")
    args = ap.parse_args(argv)

    if args.cmd == "errors":
        _print_rows(error_bursts(read_access()))
    elif args.cmd == "slow":
        _print_rows(slow_for_users(read_access(), read_app()))
    elif args.cmd == "bruteforce":
        _print_rows(bruteforce(read_auth()))
    elif args.cmd == "user":
        _print_rows(user_activity(read_app(), args.user))
    elif args.cmd == "trace":
        t = trace(read_access(), read_app(), args.rid)
        print("nginx:")
        _print_rows(t["access"])
        print("app:")
        _print_rows(t["app"])


if __name__ == "__main__":
    main()
