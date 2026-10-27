#!/usr/bin/env python3
"""Короткий нагрузочный прогон запущенного сервера (без сторонних зависимостей).

    python scripts/web_service.py --port 8765          # в отдельном окне, лучше на копии базы
    python scripts/load_test.py --base http://127.0.0.1:8765 --users 10 25 50 --seconds 15

Каждый виртуальный пользователь в цикле выполняет типовые запросы своей роли.
В конце замеряется серверная задержка алерта: от отправки срочного самоотчёта до появления в /api/alerts.
"""
import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPORT = {"mood": 3, "anxiety": 3, "sleep": 3, "comment": "нагрузочный прогон", "urgent": False}
PATIENT_STEPS = [("GET", "/api/state", None), ("GET", "/api/neuron", None), ("GET", "/api/scales", None),
                 ("GET", "/api/state", None), ("POST", "/api/patients/1/reports", REPORT)]
DOCTOR_STEPS = [("GET", "/api/state", None), ("GET", "/api/alerts", None), ("GET", "/api/patients/1", None),
                ("GET", "/api/alerts", None), ("GET", "/api/drug-insights", None)]


def request(base, method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data=data, method=method, headers=headers), timeout=30) as response:
            payload = response.read()
            return response.status, (time.perf_counter() - started) * 1000, payload
    except urllib.error.HTTPError as error:
        return error.code, (time.perf_counter() - started) * 1000, b""
    except Exception:
        return 0, (time.perf_counter() - started) * 1000, b""


def login(base, user, password):
    status, _, payload = request(base, "POST", "/api/auth/login", body={"login": user, "password": password})
    if status != 200:
        raise SystemExit(f"Не удалось войти как {user}: HTTP {status}")
    return json.loads(payload)["token"]


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(share * (len(ordered) - 1))))]


def run_level(base, users, seconds, tokens):
    timings, errors, lock = defaultdict(list), defaultdict(int), threading.Lock()
    deadline = time.perf_counter() + seconds

    def worker(index):
        role = "doctor" if index % 5 == 0 else "patient"   # 1 врач на 4 пациентов
        steps = DOCTOR_STEPS if role == "doctor" else PATIENT_STEPS
        step = index
        while time.perf_counter() < deadline:
            method, path, body = steps[step % len(steps)]
            step += 1
            status, ms, _ = request(base, method, path, tokens[role], body)
            key = f"{method} {path}"
            with lock:
                timings[key].append(ms)
                if status not in (200, 201):
                    errors[key] += 1

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(users)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - started
    everything = [ms for values in timings.values() for ms in values]
    return {
        "users": users, "requests": len(everything), "rps": len(everything) / elapsed,
        "p50": percentile(everything, .5), "p95": percentile(everything, .95), "p99": percentile(everything, .99),
        "errors": sum(errors.values()), "by_endpoint": {key: (statistics.median(values), percentile(values, .95), len(values)) for key, values in timings.items()},
    }


def alert_latency(base, tokens, attempts=5):
    results = []
    for _ in range(attempts):
        _, _, before = request(base, "GET", "/api/alerts", tokens["doctor"])
        known = {item["id"] for item in json.loads(before)["alerts"]}
        started = time.perf_counter()
        request(base, "POST", "/api/patients/1/reports", tokens["patient"], {**REPORT, "urgent": True, "comment": "проверка алерта"})
        while time.perf_counter() - started < 10:
            _, _, payload = request(base, "GET", "/api/alerts", tokens["doctor"])
            if any(item["id"] not in known for item in json.loads(payload)["alerts"]):
                results.append((time.perf_counter() - started) * 1000)
                break
            time.sleep(0.01)
    return results


def main():
    parser = argparse.ArgumentParser(description="Нагрузочный прогон Клинического компаса")
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--users", type=int, nargs="+", default=[10, 25, 50])
    parser.add_argument("--seconds", type=int, default=15)
    args = parser.parse_args()
    tokens = {"doctor": login(args.base, "doctor", "doctor2026"), "patient": login(args.base, "patient", "patient2026")}

    print(f"Сервер: {args.base} · длительность ступени: {args.seconds} с\n")
    print("| Пользователей | Запросов | RPS | p50, мс | p95, мс | p99, мс | Ошибки |")
    print("|---|---|---|---|---|---|---|")
    levels = [run_level(args.base, users, args.seconds, tokens) for users in args.users]
    for level in levels:
        print(f"| {level['users']} | {level['requests']} | {level['rps']:.0f} | {level['p50']:.0f} | {level['p95']:.0f} | {level['p99']:.0f} | {level['errors']} |")
    print("\nПо запросам на максимальной ступени (медиана / p95, мс):")
    for key, (median, p95, count) in sorted(levels[-1]["by_endpoint"].items()):
        print(f"- {key}: {median:.0f} / {p95:.0f} ({count})")
    latency = alert_latency(args.base, tokens)
    if latency:
        print(f"\nАлерт на сервере (отчёт → виден в /api/alerts): медиана {statistics.median(latency):.0f} мс, максимум {max(latency):.0f} мс, попыток {len(latency)}")


if __name__ == "__main__":
    main()
