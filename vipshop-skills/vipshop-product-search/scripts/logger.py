#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品搜索日志上报模块

用于上报商品搜索流程中的关键事件，便于排查问题。
"""

import json
import platform
import sys
import threading
import time
import urllib.request
import urllib.error
from typing import Optional
from urllib.parse import urlencode

# 导入 mars_cid
from mars_cid_generator import get_mars_cid


class LoggerReporter:
    """日志上报器"""

    # 上报地址
    REPORT_URL = "https://stat.vipstatic.com/h5front/report"
    REPORT_URL_PC = "https://stat.vip.com/h5front/report"

    # 版本号
    VERSION = "1.0.0"

    # 事件名统一前缀
    EVENT_PREFIX = "vskill_"

    def __init__(self):
        self._mars_cid = None
        self._session_id = self._generate_session_id()
        self._threads = []  # 追踪所有发送线程

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return f"{int(time.time())}_{id(self)}"

    def _get_mars_cid(self) -> str:
        """获取 mars_cid"""
        if self._mars_cid is None:
            try:
                self._mars_cid = get_mars_cid()
            except Exception:
                self._mars_cid = "unknown"
        return self._mars_cid

    def _mask_keyword(self, keyword: Optional[str]) -> str:
        """脱敏搜索关键词

        保留前2个字符，其余用***替代
        """
        if not keyword:
            return ""
        if len(keyword) <= 2:
            return keyword[:1] + "***"
        return keyword[:2] + "***"

    def _mask_product_id(self, product_id: Optional[str]) -> str:
        """脱敏商品ID

        保留前4位和后4位，中间用***替代
        """
        if not product_id:
            return ""
        if len(product_id) <= 8:
            return product_id[:4] + "***"
        return product_id[:4] + "***" + product_id[-4:]

    def _build_params(self, event: str, level: str, **kwargs) -> dict:
        """构建上报参数"""
        # 自动拼接事件前缀（已有前缀则不加）
        if self.EVENT_PREFIX and not event.startswith(self.EVENT_PREFIX):
            event = f"{self.EVENT_PREFIX}{event}"
        params = {
            "report_type": "aiclaw_search",
            "mars_cid": self._get_mars_cid(),
            "log_level": level,
            "event": event,
            "timestamp": str(int(time.time())),
            "version": self.VERSION,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
            "session_id": self._session_id,
        }

        # 脱敏处理搜索关键词
        if "keyword" in kwargs:
            params["keyword_mask"] = self._mask_keyword(kwargs.pop("keyword"))

        # 脱敏处理商品ID
        if "product_id" in kwargs:
            params["product_id_mask"] = self._mask_product_id(kwargs.pop("product_id"))

        # 脱敏处理商品ID列表
        if "product_ids" in kwargs:
            product_ids = kwargs.pop("product_ids")
            if isinstance(product_ids, list):
                params["product_ids_count"] = str(len(product_ids))
            else:
                params["product_ids_count"] = "0"

        # 添加其他字段
        params.update(kwargs)

        return params

    def _send_async(self, params: dict):
        """异步发送日志（不阻塞主流程）"""

        def send():
            try:
                # 选择上报地址
                url = self.REPORT_URL

                # 构建 URL
                query_string = urlencode(params)
                full_url = f"{url}?{query_string}"

                # 发送 GET 请求
                req = urllib.request.Request(
                    full_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )

                with urllib.request.urlopen(req, timeout=5) as response:
                    # 静默处理，不关心响应
                    pass

            except Exception:
                # 上报失败静默处理，不影响主流程
                pass

        # 在新线程中发送
        thread = threading.Thread(target=send, daemon=True)
        thread.start()
        # 清理已结束的线程，避免长期运行时列表无限增长
        self._threads = [t for t in self._threads if t.is_alive()]
        self._threads.append(thread)

    def flush(self, timeout: float = 3.0):
        """等待所有待发日志完成（退出前调用，确保日志不丢失）"""
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    def log(self, level: str, event: str, **kwargs):
        """记录日志并上报"""
        params = self._build_params(event, level, **kwargs)
        self._send_async(params)

    def debug(self, event: str, **kwargs):
        """调试级别日志"""
        self.log("DEBUG", event, **kwargs)

    def info(self, event: str, **kwargs):
        """信息级别日志"""
        self.log("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs):
        """警告级别日志"""
        self.log("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs):
        """错误级别日志"""
        self.log("ERROR", event, **kwargs)


# 全局日志上报实例
_reporter: Optional[LoggerReporter] = None


def get_reporter() -> LoggerReporter:
    """获取全局日志上报实例"""
    global _reporter
    if _reporter is None:
        _reporter = LoggerReporter()
    return _reporter


# 便捷函数
def debug(event: str, **kwargs):
    """调试级别日志"""
    get_reporter().debug(event, **kwargs)


def info(event: str, **kwargs):
    """信息级别日志"""
    get_reporter().info(event, **kwargs)


def warning(event: str, **kwargs):
    """警告级别日志"""
    get_reporter().warning(event, **kwargs)


def error(event: str, **kwargs):
    """错误级别日志"""
    get_reporter().error(event, **kwargs)


def flush(timeout: float = 3.0):
    """等待所有待发日志完成（退出前调用，确保日志不丢失）"""
    get_reporter().flush(timeout=timeout)


if __name__ == "__main__":
    # 测试代码
    print("商品搜索日志上报模块测试")
    print("-" * 50)

    # 测试不同级别的日志
    info("search_start", keyword="连衣裙", page_offset=0)
    warning("search_slow", keyword="连衣裙", elapsed_ms=5000)
    error("search_failed", keyword="连衣裙", error_msg="接口超时", product_ids=["1234567890", "0987654321"])

    print("日志已发送（异步）")
    print("等待 2 秒确保发送完成...")
    time.sleep(2)
