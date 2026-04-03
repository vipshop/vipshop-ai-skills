#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唯品会扫码登录主模块

整合二维码获取、展示、状态轮询和Cookie管理的完整登录流程。

API接口信息：
- 初始化二维码: POST https://passport.vip.com/qrLogin/initQrLogin
- 获取二维码图片: GET https://passport.vip.com/qrLogin/getQrImage?qrToken=xxx
- 轮询状态: POST https://passport.vip.com/qrLogin/checkStatus
"""

import sys
import time
import os
import argparse
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

# 设置 stdout 编码为 UTF-8，解决 Windows 下中文显示问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests

# 导入子模块
from token_manager import TokenManager, TokenInfo
from qr_code_client import QRCodeClient
from status_poller import StatusPoller, LoginStatus, StatusResult
from mars_cid_generator import get_mars_cid  # AI-Generated: 导入 mars_cid 生成器


# =============================================================================
# 配置参数
# =============================================================================

class Config:
    """配置类"""
    # API 基础配置
    BASE_URL = "https://passport.vip.com"
    INIT_QR_ENDPOINT = "/qrLogin/initQrLogin"
    GET_QR_IMAGE_ENDPOINT = "/qrLogin/getQrImage"
    CHECK_STATUS_ENDPOINT = "/qrLogin/checkStatus"
    
    # 轮询配置
    POLL_INTERVAL = 1  # 轮询间隔（秒），建议每秒轮询一次
    POLL_TIMEOUT = 180  # 轮询超时时间（秒），二维码有效期3分钟
    
    # 二维码配置
    SHOW_IN_TERMINAL = False  # 是否在终端显示二维码（False则打开图片）
    
    # 交互模式配置
    NON_BLOCKING_MODE = True  # 默认使用非阻塞模式（发送二维码后不等待，直接结束）


# =============================================================================
# VIP 登录管理器
# =============================================================================

@dataclass
class LoginResult:
    """登录结果"""
    success: bool
    message: str = ""
    qr_token: Optional[str] = None
    redirect_url: Optional[str] = None


class VIPLoginManager:
    """VIP登录管理器 - 整合完整登录流程"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化登录管理器
        
        Args:
            config: 配置对象，默认使用内置Config
        """
        self.config = config or Config()
        
        # 创建共享session以保持Cookie会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': f'{self.config.BASE_URL}/',
            'Origin': self.config.BASE_URL,
            'Content-Type': 'application/x-www-form-urlencoded',  # AI-Generated: 必须设置
        })
        
        mars_cid = get_mars_cid()
        self.session.cookies.set('mars_cid', mars_cid, domain='.vip.com')
        
        # 初始化各模块，传入共享session
        self.qr_client = QRCodeClient(
            base_url=self.config.BASE_URL,
            init_endpoint=self.config.INIT_QR_ENDPOINT,
            image_endpoint=self.config.GET_QR_IMAGE_ENDPOINT,
            session=self.session
        )
        
        self.status_poller = StatusPoller(
            base_url=self.config.BASE_URL,
            check_endpoint=self.config.CHECK_STATUS_ENDPOINT,
            poll_interval=self.config.POLL_INTERVAL,
            timeout=self.config.POLL_TIMEOUT,
            session=self.session
        )
        
        self.token_manager = TokenManager()
    
    def login(self,
              where_from: str = "",
              show_qr_callback: Optional[Callable] = None,
              status_callback: Optional[Callable[[str], None]] = None,
              send_qr_to_user_callback: Optional[Callable[[bytes, str], None]] = None,
              qr_token_to_poll: Optional[str] = None,
              blocking_mode: Optional[bool] = None) -> LoginResult:
        """
        执行完整的扫码登录流程

        Args:
            where_from: 请求来源标识（可选）
            show_qr_callback: 显示二维码的回调函数
            status_callback: 状态变更回调函数
            send_qr_to_user_callback: 发送二维码图片给用户的回调函数，接收(image_bytes, image_format)
                                     提供此回调时，发送完图片后脚本会直接结束，不会进入轮询
            qr_token_to_poll: 指定要轮询的qrToken（用于继续之前的登录流程）
            blocking_mode: 是否使用阻塞模式（轮询等待登录完成），None则使用Config.NON_BLOCKING_MODE默认值

        Returns:
            登录结果
        """
        # 如果提供了 qr_token_to_poll，直接进入轮询阶段
        if qr_token_to_poll:
            print("=" * 60)
            print("唯品会扫码登录 - 继续轮询")
            print("=" * 60)
            return self._poll_and_complete(qr_token_to_poll, where_from, status_callback)

        print("=" * 60)
        print("唯品会扫码登录")
        print("=" * 60)

        # 步骤1: 初始化二维码
        print("\n[1/3] 正在获取登录二维码...")
        success, qr_token, init_data = self.qr_client.init_qr_code(where_from=where_from)

        if not success or not qr_token:
            return LoginResult(
                success=False,
                message=f"获取二维码失败: {init_data}"
            )

        print(f"[1/3] ✓ 获取qrToken成功")

        # 步骤2: 获取并展示二维码
        print("\n[2/3] 正在获取二维码图片...")
        success, image_bytes, image_format = self.qr_client.get_qr_image(qr_token=qr_token)

        if not success or not image_bytes:
            # 尝试使用备用方案：生成二维码
            print("[2/3] 使用备用方案生成二维码...")
            qr_url = self.qr_client.get_qr_image_url(qr_token)
            img = self.qr_client.generate_qr_from_string(qr_url, size=300)

            import io
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
            image_format = 'png'

        # 保存二维码图片到文件（供 OpenClaw 读取发送）
        qr_file_path = self.qr_client.save_qr_image(image_bytes, image_format)
        
        # 展示二维码
        if show_qr_callback:
            show_qr_callback(image_bytes, image_format)
        elif self.config.SHOW_IN_TERMINAL:
            self.qr_client.display_qr_in_terminal(image_bytes)
        else:
            self.qr_client.open_qr_image(image_bytes, image_format)
        
        # 获取二维码链接
        qr_url = self.qr_client.get_qr_image_url(qr_token)
        
        # OpenClaw 环境：尝试发送图片 + 打印链接
        if os.environ.get('OPENCLAW_SESSION') == '1' and qr_file_path:
            print(f"\n[OPENCLAW_SEND_FILE]{qr_file_path}[/OPENCLAW_SEND_FILE]")
        
        # 所有平台都打印二维码链接
        print(f"\n🔗 二维码链接: {qr_url}")
        print(f"\n📱 请使用唯品会APP扫描上方二维码完成登录")
        print(f"\n💡 提示：点击链接可在浏览器中打开二维码")
        print(f"\n🔑 扫码确认后，使用命令: python scripts/vip_login.py --poll {qr_token}")

        # 确定是否使用阻塞模式
        use_blocking = blocking_mode if blocking_mode is not None else not self.config.NON_BLOCKING_MODE

        # 非阻塞模式：发送二维码后直接结束（不轮询）
        if not use_blocking:
            # 如果有send_qr_to_user_callback，调用它发送二维码
            if send_qr_to_user_callback:
                print("\n[2/3] 正在发送二维码给用户...")
                send_qr_to_user_callback(image_bytes, image_format)
                print("[2/3] ✓ 二维码已发送给用户")
            
            print(f"\n[3/3] 请使用唯品会APP扫描二维码")
            print(f"      扫码确认后，使用以下命令完成登录：")
            print(f"      python scripts/vip_login.py --poll {qr_token}")

            # 保存qrToken以便后续轮询
            self._save_pending_login(qr_token, where_from)

            # 非阻塞模式，直接返回
            return LoginResult(
                success=True,
                message="二维码已发送，请扫码确认后使用 --poll 参数继续",
                qr_token=qr_token
            )

        # 阻塞模式：继续轮询
        # 如果有send_qr_to_user_callback，发送二维码给用户
        if send_qr_to_user_callback:
            print("\n[2/3] 正在发送二维码给用户...")
            send_qr_to_user_callback(image_bytes, image_format)
            print("[2/3] ✓ 二维码已发送给用户")
        
        print("[2/3] ✓ 请使用唯品会APP扫描二维码")

        # 步骤3: 轮询状态
        print("\n[3/3] 等待扫码确认...")
        
        def on_status_change(result: StatusResult):
            if status_callback:
                status_callback(f"状态: {result.message}")
        
        def on_scanned(result: StatusResult):
            print(f"\n[3/3] ✓ 用户已扫码")
            print("[3/3] 等待用户确认登录...")
        
        def on_confirmed(result: StatusResult):
            print(f"\n[3/3] ✓ 登录已确认!")
        
        poll_result = self.status_poller.poll_until_complete(
            qr_token=qr_token,
            where_from=where_from,
            on_status_change=on_status_change,
            on_scanned=on_scanned,
            on_confirmed=on_confirmed
        )
        
        # 检查轮询结果
        if poll_result.status != LoginStatus.CONFIRMED:
            message = poll_result.message
            if poll_result.status == LoginStatus.INVALID:
                message = "二维码已失效，请重新登录"
            
            return LoginResult(success=False, message=message, qr_token=qr_token)
        
        # 从登录确认响应中提取cookies (set-cookie headers)
        # 只保存必要的cookie：PASSPORT_ACCESS_TOKEN 和 mars_cid
        cookies = {}
        expires_at = 0.0  # PASSPORT_ACCESS_TOKEN 的过期时间戳
        
        if poll_result.raw_http_response is not None:
            # 从响应头中提取set-cookie (可能有多个)
            # 使用raw._original_response.headers.get_all获取多个Set-Cookie
            try:
                set_cookie_headers = poll_result.raw_http_response.raw._original_response.headers.get_all('Set-Cookie')
            except AttributeError:
                # 如果不支持get_all，尝试用get获取单个
                set_cookie_header = poll_result.raw_http_response.headers.get('Set-Cookie', '')
                set_cookie_headers = [set_cookie_header] if set_cookie_header else []
            
            for cookie_str in set_cookie_headers:
                if not cookie_str:
                    continue
                # 提取cookie名称和值 (第一个=前的部分和第一个=后的部分，直到;)
                if '=' in cookie_str:
                    parts = cookie_str.split(';')[0].split('=', 1)
                    if len(parts) == 2:
                        cookie_name, cookie_value = parts
                        cookie_name = cookie_name.strip()
                        # 只保存 PASSPORT_ACCESS_TOKEN
                        if cookie_name == 'PASSPORT_ACCESS_TOKEN':
                            cookies[cookie_name] = cookie_value.strip()
                            # 解析 Max-Age
                            for attr in cookie_str.split(';'):
                                attr = attr.strip()
                                if attr.startswith('Max-Age='):
                                    try:
                                        max_age = int(attr.split('=', 1)[1])
                                        expires_at = time.time() + max_age
                                    except (ValueError, IndexError):
                                        pass
                                elif attr.startswith('Expires='):
                                    try:
                                        from email.utils import parsedate_to_datetime
                                        exp_str = attr.split('=', 1)[1]
                                        exp_dt = parsedate_to_datetime(exp_str)
                                        expires_at = exp_dt.timestamp()
                                    except Exception:
                                        pass
            
            # 同时获取session中的cookies，只保留 mars_cid
            session_cookies = self.session.cookies.get_dict()
            if 'mars_cid' in session_cookies:
                cookies['mars_cid'] = session_cookies['mars_cid']
        else:
            # 从session中获取，只保留必要的cookie
            session_cookies = self.session.cookies.get_dict()
            if 'PASSPORT_ACCESS_TOKEN' in session_cookies:
                cookies['PASSPORT_ACCESS_TOKEN'] = session_cookies['PASSPORT_ACCESS_TOKEN']
            if 'mars_cid' in session_cookies:
                cookies['mars_cid'] = session_cookies['mars_cid']
        
        # 保存登录态（只包含必要的cookie）
        token_info = TokenInfo(
            cookies=cookies,
            user_id='',  # 不再保存用户ID
            nickname='',  # 不再保存昵称
            expires_at=expires_at
        )

        # 保存到本地（单用户模式）
        self.token_manager.save_token("current_user", token_info)

        # 清理二维码文件
        self.qr_client.cleanup_qr_files()

        return LoginResult(
            success=True,
            message="登录成功",
            qr_token=qr_token,
            redirect_url=poll_result.redirect_url
        )

    def _save_pending_login(self, qr_token: str, where_from: str):
        """保存待处理的登录信息，以便后续轮询"""
        import json
        from pathlib import Path
        
        pending_file = Path.home() / ".vipshop-user-login" / "pending_login.json"
        pending_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "qr_token": qr_token,
            "where_from": where_from,
            "created_at": time.time()
        }
        
        with open(pending_file, 'w') as f:
            json.dump(data, f)
    
    def _load_pending_login(self) -> Optional[Dict[str, Any]]:
        """加载待处理的登录信息"""
        import json
        from pathlib import Path
        
        pending_file = Path.home() / ".vipshop-user-login" / "pending_login.json"
        
        if not pending_file.exists():
            return None
        
        try:
            with open(pending_file, 'r') as f:
                data = json.load(f)
            
            # 检查是否过期（超过3分钟视为过期）
            if time.time() - data.get("created_at", 0) > 180:
                pending_file.unlink()
                return None
            
            return data
        except (json.JSONDecodeError, IOError):
            return None
    
    def _clear_pending_login(self):
        """清除待处理的登录信息"""
        from pathlib import Path
        pending_file = Path.home() / ".vipshop-user-login" / "pending_login.json"
        if pending_file.exists():
            pending_file.unlink()
    
    def _poll_and_complete(self, qr_token: str, where_from: str = "", 
                           status_callback: Optional[Callable[[str], None]] = None) -> LoginResult:
        """执行轮询和登录完成流程"""
        
        def on_status_change(result: StatusResult):
            if status_callback:
                status_callback(f"状态: {result.message}")
        
        def on_scanned(result: StatusResult):
            print(f"\n  ✓ 用户已扫码")
            print("  等待用户确认登录...")
        
        def on_confirmed(result: StatusResult):
            print(f"\n  ✓ 登录已确认!")
        
        print("\n[轮询] 正在检查登录状态...")
        
        poll_result = self.status_poller.poll_until_complete(
            qr_token=qr_token,
            where_from=where_from,
            on_status_change=on_status_change,
            on_scanned=on_scanned,
            on_confirmed=on_confirmed
        )
        
        # 检查轮询结果
        if poll_result.status != LoginStatus.CONFIRMED:
            message = poll_result.message
            if poll_result.status == LoginStatus.INVALID:
                message = "二维码已失效，请重新登录"
            
            return LoginResult(success=False, message=message, qr_token=qr_token)
        
        # 从登录确认响应中提取cookies
        # 只保存必要的cookie：PASSPORT_ACCESS_TOKEN 和 mars_cid
        cookies = {}
        expires_at = 0.0
        
        if poll_result.raw_http_response is not None:
            try:
                set_cookie_headers = poll_result.raw_http_response.raw._original_response.headers.get_all('Set-Cookie')
            except AttributeError:
                set_cookie_header = poll_result.raw_http_response.headers.get('Set-Cookie', '')
                set_cookie_headers = [set_cookie_header] if set_cookie_header else []
            
            for cookie_str in set_cookie_headers:
                if not cookie_str:
                    continue
                if '=' in cookie_str:
                    parts = cookie_str.split(';')[0].split('=', 1)
                    if len(parts) == 2:
                        cookie_name, cookie_value = parts
                        cookie_name = cookie_name.strip()
                        # 只保存 PASSPORT_ACCESS_TOKEN
                        if cookie_name == 'PASSPORT_ACCESS_TOKEN':
                            cookies[cookie_name] = cookie_value.strip()
                            # 解析 Max-Age
                            for attr in cookie_str.split(';'):
                                attr = attr.strip()
                                if attr.startswith('Max-Age='):
                                    try:
                                        max_age = int(attr.split('=', 1)[1])
                                        expires_at = time.time() + max_age
                                    except (ValueError, IndexError):
                                        pass
                                elif attr.startswith('Expires='):
                                    try:
                                        from email.utils import parsedate_to_datetime
                                        exp_str = attr.split('=', 1)[1]
                                        exp_dt = parsedate_to_datetime(exp_str)
                                        expires_at = exp_dt.timestamp()
                                    except Exception:
                                        pass
            
            # 同时获取session中的cookies，只保留 mars_cid
            session_cookies = self.session.cookies.get_dict()
            if 'mars_cid' in session_cookies:
                cookies['mars_cid'] = session_cookies['mars_cid']
        else:
            # 从session中获取，只保留必要的cookie
            session_cookies = self.session.cookies.get_dict()
            if 'PASSPORT_ACCESS_TOKEN' in session_cookies:
                cookies['PASSPORT_ACCESS_TOKEN'] = session_cookies['PASSPORT_ACCESS_TOKEN']
            if 'mars_cid' in session_cookies:
                cookies['mars_cid'] = session_cookies['mars_cid']
        
        # 保存登录态（只包含必要的cookie）
        token_info = TokenInfo(
            cookies=cookies,
            user_id='',  # 不再保存用户ID
            nickname='',  # 不再保存昵称
            expires_at=expires_at
        )

        self.token_manager.save_token("current_user", token_info)
        self._clear_pending_login()
        self.qr_client.cleanup_qr_files()

        # 显示过期时间
        expire_readable = token_info.expire_datetime
        print(f"\n⏰ Token过期时间: {expire_readable}")

        return LoginResult(
            success=True,
            message="登录成功",
            qr_token=qr_token,
            redirect_url=poll_result.redirect_url
        )
    
    def quick_login(self, where_from: str = "") -> LoginResult:
        """
        快速登录 - 一键完成整个流程
        
        Args:
            where_from: 请求来源标识（可选）
            
        Returns:
            登录结果
        """
        return self.login(where_from=where_from)
    
    def get_stored_token(self, token_id: str) -> Optional[TokenInfo]:
        """
        获取已存储的token
        
        Args:
            token_id: Token标识
            
        Returns:
            Token信息
        """
        return self.token_manager.get_token(token_id)
    
    def list_logged_in_tokens(self):
        """列出所有已登录的token"""
        return self.token_manager.list_users()
    
    def print_login_summary(self):
        """打印登录状态摘要"""
        self.token_manager.print_all_tokens()


# =============================================================================
# 命令行接口
# =============================================================================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='唯品会扫码登录工具（默认非阻塞模式）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python vip_login.py                    # 执行扫码登录（非阻塞，获取二维码后结束）
  python vip_login.py --blocking         # 阻塞模式（获取二维码后等待扫码完成）
  python vip_login.py --where-from xxx   # 指定请求来源
  python vip_login.py --list             # 列出已登录记录
  python vip_login.py --status           # 查看登录状态
  python vip_login.py --poll TOKEN       # 继续轮询指定qrToken
  python vip_login.py --continue         # 继续上次未完成的登录
        """
    )
    
    parser.add_argument('--where-from', '-w', 
                       help='请求来源标识')
    parser.add_argument('--list', '-l', 
                       action='store_true', 
                       help='列出已登录的记录')
    parser.add_argument('--status', '-s', 
                       action='store_true', 
                       help='查看登录状态')
    parser.add_argument('--logout', 
                       metavar='TOKEN_ID', 
                       help='注销指定登录记录')
    parser.add_argument('--terminal', '-t',
                       action='store_true',
                       help='在终端显示二维码（而不是打开图片）')
    parser.add_argument('--poll', 
                       metavar='QR_TOKEN',
                       help='指定qrToken继续轮询登录状态')
    parser.add_argument('--continue', '-c',
                       dest='continue_login',
                       action='store_true',
                       help='继续上次未完成的登录（从pending_login.json读取qrToken）')
    parser.add_argument('--blocking', '-b',
                       action='store_true',
                       help='使用阻塞模式（获取二维码后等待扫码完成，不立即结束）')
    
    args = parser.parse_args()
    
    # 创建登录管理器
    config = Config()
    if args.terminal:
        config.SHOW_IN_TERMINAL = True
    if args.blocking:
        config.NON_BLOCKING_MODE = False
    
    manager = VIPLoginManager(config)
    
    # 处理命令
    if args.list:
        tokens = manager.list_logged_in_tokens()
        if tokens:
            print("已登录的记录:")
            for token in tokens:
                print(f"  - {token}")
        else:
            print("没有已登录的记录")
        return
    
    if args.status:
        manager.print_login_summary()
        return
    
    if args.logout:
        manager.token_manager.remove_token(args.logout)
        print(f"已注销: {args.logout}")
        return
    
    # 处理继续登录
    if args.continue_login:
        pending = manager._load_pending_login()
        if pending:
            print(f"继续登录流程，qrToken: {pending['qr_token'][:20]}...")
            result = manager.login(
                where_from=pending.get('where_from', 'AIClaw'),
                qr_token_to_poll=pending['qr_token']
            )
        else:
            print("没有待处理的登录请求")
            sys.exit(1)
    elif args.poll:
        # 使用指定的qrToken继续轮询
        result = manager.login(
            where_from=args.where_from or "AIClaw",
            qr_token_to_poll=args.poll
        )
    else:
        # 执行新的登录
        where_from = args.where_from or "AIClaw"
        result = manager.login(where_from=where_from)
    
    print("\n" + "=" * 60)
    if result.success:
        if result.message == "二维码已发送，请扫码确认后使用 --poll 参数继续":
            print(f"ℹ {result.message}")
            print(f"  qrToken: {result.qr_token}")
        else:
            print(f"✓ {result.message}")
    else:
        print(f"✗ 登录失败: {result.message}")
    print("=" * 60)
    
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
