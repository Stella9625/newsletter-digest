"""HTTP 服务器：托管 output/ 目录下的 RSS XML 文件"""

import logging
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

from src.config import OUTPUT_DIR, SERVER_HOST, SERVER_PORT

logger = logging.getLogger(__name__)


class RSSHandler(SimpleHTTPRequestHandler):
    """自定义 handler，为 .xml 文件设置正确的 Content-Type"""

    def end_headers(self):
        # 为 XML 文件设置正确的 MIME 类型，让 RSS 阅读器正确识别
        if self.path.endswith(".xml"):
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        super().end_headers()

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # SimpleHTTPRequestHandler 的 directory 参数指定服务根目录
    handler = partial(RSSHandler, directory=str(OUTPUT_DIR))

    server = HTTPServer((SERVER_HOST, SERVER_PORT), handler)
    logger.info(f"RSS 服务器启动: http://localhost:{SERVER_PORT}")
    logger.info(f"  日报订阅: http://localhost:{SERVER_PORT}/daily-digest.xml")
    logger.info(f"  文章订阅: http://localhost:{SERVER_PORT}/articles.xml")
    logger.info(f"  托管目录: {OUTPUT_DIR}")
    logger.info("按 Ctrl+C 停止")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务器已停止")
        server.server_close()


if __name__ == "__main__":
    main()
