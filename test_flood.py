import time
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error

# Trang cần test tải nặng (đọc database thật)
URL = "http://127.0.0.1:5000/products"

# Các mức tải tăng dần để thử độ chịu đựng
STRESS_LEVELS = [
    {"users": 10,  "total": 50},    # Mức nhẹ: 10 user bấm 50 lần
    {"users": 30,  "total": 150},   # Mức vừa: 30 user bấm 150 lần
    {"users": 70,  "total": 350},   # Mức cao: 70 user bấm 350 lần
    {"users": 150, "total": 600},   # Mức cực hạn: 150 user dồn dập
    {"users": 15000, "total": 100000},   # Mức vip pro max
]

def send_request():
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "StressTester/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            latency = (time.perf_counter() - t0) * 1000
            return response.getcode(), latency
    except urllib.error.HTTPError as e:
        latency = (time.perf_counter() - t0) * 1000
        return e.code, latency
    except Exception:
        # Khi server quá tải, timeout hoặc từ chối kết nối
        latency = (time.perf_counter() - t0) * 1000
        return "CRASH/TIMEOUT", latency

print(f"🔥 BẮT ĐẦU THỬ THÁCH SỨC CHỊU ĐỰNG SERVER: {URL}\n" + "=" * 65)

for level in STRESS_LEVELS:
    users = level["users"]
    total = level["total"]
    print(f"\n🚀 Đang test mức: {users} người dùng đồng thời (Tổng {total} requests)...")

    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as executor:
        results = list(executor.map(lambda _: send_request(), range(total)))
    duration = time.perf_counter() - start_time

    # Thống kê kết quả
    ok_count = sum(1 for code, _ in results if code == 200)
    limit_count = sum(1 for code, _ in results if code == 429)
    crash_count = sum(1 for code, _ in results if code in [500, 502, 503, "CRASH/TIMEOUT"])
    avg_latency = sum(lat for _, lat in results) / len(results)

    print(f"   ⏱️ Thời gian chạy: {duration:.2f}s | Tốc độ: {total/duration:.1f} req/s")
    print(f"   📊 Độ trễ phản hồi trung bình: {avg_latency:.1f} ms")
    print(f"   ✅ Thành công (200 OK): {ok_count}/{total}")
    if limit_count > 0:
        print(f"   🛑 Rate Limit bảo vệ (429): {limit_count} requests")
    if crash_count > 0:
        print(f"   ⚠️ LỖI QUÁ TẢI / SẬP (Crash/Timeout): {crash_count} requests <-- BẮT ĐẦU ĐUỐI!")
    else:
        print(f"   💪 Server vẫn đứng vững 100%!")
