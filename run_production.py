import logging
from waitress import serve
from web import app

# Tắt bớt log rác khi stress test để đạt tốc độ tối đa
logging.getLogger('waitress').setLevel(logging.ERROR)

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ĐANG CHẠY PRODUCTION WSGI SERVER (WAITRESS - ĐA LUỒNG)")
    print("⚡ Số luồng xử lý đồng thời (Threads): 16")
    print("🌐 Website đang lắng nghe tại: http://127.0.0.1:5000")
    print("=" * 60)
    serve(
        app,
        host='127.0.0.1',
        port=5000,
        threads=16,
        connection_limit=1000,
        channel_timeout=30
    )
