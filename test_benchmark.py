import time
import sys
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

URL = "http://127.0.0.1:5000/products"

STRESS_LEVELS = [
    {"users": 10,  "total": 50},
    {"users": 30,  "total": 150},
    {"users": 60,  "total": 300},
]

def send_request():
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Benchmark/1.0"})
        # Đặt timeout hợp lý để tránh bị timeout giả khi nhiều luồng xếp hàng
        with urllib.request.urlopen(req, timeout=10) as response:
            latency = (time.perf_counter() - t0) * 1000
            return response.getcode(), latency
    except urllib.error.HTTPError as e:
        latency = (time.perf_counter() - t0) * 1000
        return e.code, latency
    except Exception as e:
        latency = (time.perf_counter() - t0) * 1000
        return f"ERR:{type(e).__name__}", latency

print(f"BẮT ĐẦU BENCHMARK KIỂM TRA HIỆU NĂNG TỚI: {URL}\n" + "=" * 65)

for level in STRESS_LEVELS:
    users = level["users"]
    total = level["total"]
    print(f"\n Đang test: {users} luồng đồng thời (Tổng {total} requests)...")

    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as executor:
        results = list(executor.map(lambda _: send_request(), range(total)))
    duration = time.perf_counter() - start_time

    ok_count = sum(1 for code, _ in results if code == 200)
    limit_count = sum(1 for code, _ in results if code == 429)
    err_count = sum(1 for code, _ in results if code not in [200, 429])
    avg_latency = sum(lat for _, lat in results) / len(results) if results else 0

    print(f"    Thời gian chạy: {duration:.2f}s | Tốc độ: {total/duration:.1f} req/s")
    print(f"    Độ trễ trung bình: {avg_latency:.1f} ms")
    print(f"    Thành công (200 OK): {ok_count}/{total}")
    if limit_count > 0:
        print(f"    Bị Rate Limiter chặn (429): {limit_count}/{total}")
    if err_count > 0:
        print(f"    Lỗi kết nối / Server nghẽn: {err_count}/{total}")
    else:
        print(f"    Server xử lý mượt mà 100%!")

print("\n" + "=" * 65 + "\n HOÀN TẤT BÀI TEST!")
