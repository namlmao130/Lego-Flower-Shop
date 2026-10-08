import logging
from waitress import serve
from web import app

# Tắt bớt log rác khi stress test để đạt tốc độ tối đa
logging.getLogger('waitress').setLevel(logging.ERROR)

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ĐANG CHẠY PRODUCTION WSGI SERVER (WAITRESS - HIỆU NĂNG CAO)")
    print("⚡ Số luồng xử lý đồng thời (Threads): 32")
    print("⚡ Giới hạn kết nối (Connection Limit): 2,000")
    print("⚡ Hàng đợi Socket Backlog: 2,048")
    print("🌐 Website đang lắng nghe tại: http://127.0.0.1:5000")
    print("=" * 60)
    serve(
        app,
        host='127.0.0.1',
        port=5000,
        threads=32,
        connection_limit=2000,
        backlog=2048,
        channel_timeout=20,
        cleanup_interval=30,
        inbuf_overflow=524288,
        outbuf_overflow=1048576,
    )
