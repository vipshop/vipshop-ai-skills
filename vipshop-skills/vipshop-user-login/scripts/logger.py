#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志上报模块

用于上报登录流程中的关键事件，便于排查问题。
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

    def __init__(self):
        self._mars_cid = None
        self._lock = threading.Lock()
        self._session_id = self._generate_session_id()

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

    def _mask_qr_token(self, qr_token: Optional[str]) -> str:
        """脱敏 qrToken

        例如: 10000-098f1e2676a54ef0bbdb43e18c6ef84a -> 10000-098f1***
        """
        if not qr_token:
            return ""
        if len(qr_token) <= 10:
            return qr_token[:5] + "***"
        return qr_token[:10] + "***"

    def _build_params(self, event: str, level: str, **kwargs) -> dict:
        """构建上报参数"""
        params = {
            "report_type": "aiclaw_login",
            "mars_cid": self._get_mars_cid(),
            "log_level": level,
            "event": event,
            "timestamp": str(int(time.time())),
            "version": self.VERSION,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
            "session_id": self._session_id,
        }

        # 脱敏处理 qr_token
        if "qr_token" in kwargs:
            params["qr_token_mask"] = self._mask_qr_token(kwargs.pop("qr_token"))

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


if __name__ == "__main__":
    # 测试代码
    print("日志上报模块测试")
    print("-" * 50)

    # 测试不同级别的日志
    info("test_info", message="这是一条测试信息")
    warning("test_warning", qr_token="10000-098f1e2676a54ef0bbdb43e18c6ef84a")
    error("test_error", error_msg="测试错误", retry_count=1)

    print("日志已发送（异步）")
    print("等待 2 秒确保发送完成...")
    time.sleep(2)
