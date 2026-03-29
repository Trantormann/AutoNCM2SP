"""
网易云音乐 API 封装模块
使用 pyncm 与网易云音乐 API 交互（纯 Python 实现，无 C 扩展依赖）
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import get_settings, QUALITY_ORDER, QUALITY_MAPPING
from database.models import SongInfo

try:
    from pyncm.apis.playlist import GetPlaylistInfo
    from pyncm.apis.track import GetTrackAudio, GetTrackDetail
    from pyncm.apis.login import (
        LoginViaCellphone, LoginViaEmail, GetCurrentLoginStatus,
        GetLoginQRCodeUrl, LoginQrcodeCheck, LoginQrcodeUnikey
    )
    import pyncm
    PYNCM_AVAILABLE = True
except Exception as e:
    PYNCM_AVAILABLE = False


# 音质对应的码率映射
QUALITY_BITRATE = {
    'standard': 128000,
    'higher':   192000,
    'exhigh':   320000,
    'lossless': 999000,
    'hires':    999000,
}


class NcmAPI:
    """网易云音乐 API 封装类（基于 pyncm）"""

    def __init__(self):
        """初始化 API 客户端，并尝试登录"""
        self.settings = get_settings()
        self.logged_in = False
        self.login_user = ''
        self.session_file = Path(__file__).parent.parent / 'config' / '.ncm_session'
        
        # 先尝试加载已有会话
        if not self._load_session():
            self._try_login()

    # ------------------------------------------------------------------ #
    # 会话管理
    # ------------------------------------------------------------------ #

    def _save_session(self):
        """保存登录会话到文件"""
        try:
            if hasattr(pyncm, 'GetCurrentSession'):
                session = pyncm.GetCurrentSession()
                session_data = {
                    'cookies': dict(session.cookies),
                    'headers': dict(session.headers)
                }
                self.session_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, ensure_ascii=False)
                return True
        except Exception as e:
            print(f'  [登录] 保存会话失败: {e}')
        return False

    def _load_session(self) -> bool:
        """从文件加载登录会话"""
        try:
            if not self.session_file.exists():
                return False
            
            with open(self.session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            if hasattr(pyncm, 'GetCurrentSession'):
                session = pyncm.GetCurrentSession()
                session.cookies.update(session_data.get('cookies', {}))
                session.headers.update(session_data.get('headers', {}))
                
                # 验证会话是否有效
                result = GetCurrentLoginStatus()
                if result and result.get('code') == 200:
                    profile = result.get('profile', {})
                    self.login_user = profile.get('nickname', '未知用户')
                    self.logged_in = True
                    print(f'  [登录] 已恢复登录: {self.login_user}')
                    return True
                else:
                    # 会话已过期，删除文件
                    self.session_file.unlink(missing_ok=True)
        except Exception as e:
            print(f'  [登录] 加载会话失败: {e}')
            # 删除可能损坏的会话文件
            if self.session_file.exists():
                self.session_file.unlink(missing_ok=True)
        return False

    def clear_session(self):
        """清除保存的会话"""
        if self.session_file.exists():
            self.session_file.unlink(missing_ok=True)
            print('  [登录] 已清除会话')

    # ------------------------------------------------------------------ #
    # 登录
    # ------------------------------------------------------------------ #

    def _try_login(self):
        """根据配置尝试登录，登录失败不阻塞程序"""
        login_cfg = self.settings.get_login_config()
        password = login_cfg.get('password', '').strip()
        phone    = login_cfg.get('phone', '').strip()
        email    = login_cfg.get('email', '').strip()

        if not password or (not phone and not email):
            print('  [登录] 未配置账号，以游客模式运行（仅可下载试听片段）')
            return

        try:
            if phone:
                result = LoginViaCellphone(phone=phone, password=password)
            else:
                result = LoginViaEmail(email=email, password=password)

            if result and result.get('code') == 200:
                profile = result.get('profile') or result.get('data', {}).get('profile', {})
                self.login_user = profile.get('nickname', '未知用户') if profile else '未知用户'
                self.logged_in = True
                self._save_session()  # 保存会话
                print(f'  [登录] 已登录账号: {self.login_user}')
            else:
                msg = result.get('message', '') if result else '无响应'
                # 判断是否需要验证码
                if '验证码' in msg or result.get('code') == 8821:
                    print(f'  [登录] 密码登录触发风控: {msg}')
                    print('  [登录] 尝试二维码登录...')
                    self._try_qrcode_login()
                else:
                    print(f'  [登录] 登录失败: {msg}（以游客模式继续）')
        except Exception as e:
            err_str = str(e)
            if '验证码' in err_str or '60001' in err_str or '8821' in err_str:
                print(f'  [登录] 密码登录触发风控，尝试二维码登录...')
                self._try_qrcode_login()
            else:
                print(f'  [登录] 登录异常: {e}（以游客模式继续）')

    def _try_qrcode_login(self):
        """二维码登录（绕过风控）"""
        import time
        try:
            # 获取二维码 key
            result = LoginQrcodeUnikey()
            qrcode_key = result.get('unikey') if isinstance(result, dict) else result
            if not qrcode_key:
                print('  [登录] 获取二维码失败（以游客模式继续）')
                return

            # 生成二维码 URL
            qr_url = GetLoginQRCodeUrl(qrcode_key)
            print(f'  [登录] 请使用网易云音乐 APP 扫描下方二维码登录：')
            print()
            print(f'  {qr_url}')
            print()

            # 尝试生成终端二维码
            try:
                import qrcode
                qr = qrcode.QRCode(border=2)
                qr.add_data(qr_url)
                qr.make()
                qr.print_ascii(invert=True, tty=True)
                print()
            except Exception:
                print('  （如终端无法显示二维码，请手动复制上方链接到浏览器打开）')
                print()

            # 轮询检查扫码状态
            print('  等待扫码...', end='', flush=True)
            for _ in range(60):  # 最多等待60秒
                time.sleep(1)
                status_result = LoginQrcodeCheck(qrcode_key)
                code = status_result.get('code') if isinstance(status_result, dict) else None

                if code == 803:  # 授权登录成功
                    print('  扫码成功！')
                    # 获取登录状态
                    login_result = GetCurrentLoginStatus()
                    if login_result and login_result.get('code') == 200:
                        profile = login_result.get('profile', {})
                        self.login_user = profile.get('nickname', '未知用户')
                        self.logged_in = True
                        self._save_session()  # 保存会话
                        print(f'  [登录] 已登录账号: {self.login_user}')
                        return
                elif code == 800:  # 二维码过期
                    print('  二维码已过期（以游客模式继续）')
                    return
                elif code == 801:  # 等待扫码
                    continue
                elif code == 802:  # 等待确认
                    print('  等待确认...', end='', flush=True)

            print('  扫码超时（以游客模式继续）')
        except Exception as e:
            print(f'  [登录] 二维码登录异常: {e}（以游客模式继续）')

    # ------------------------------------------------------------------ #
    # 健康检查
    # ------------------------------------------------------------------ #

    def check_health(self) -> bool:
        """检查 pyncm 是否可正常调用"""
        return PYNCM_AVAILABLE

    # ------------------------------------------------------------------ #
    # 歌单解析
    # ------------------------------------------------------------------ #

    @staticmethod
    def extract_playlist_id(playlist_url: str) -> Optional[str]:
        """
        从歌单链接中提取歌单 ID

        支持格式：
          https://music.163.com/playlist?id=123456
          https://music.163.com/#/playlist?id=123456
          直接传入数字 ID
        """
        if not playlist_url:
            return None

        match = re.search(r'[?&]id=(\d+)', playlist_url)
        if match:
            return match.group(1)

        match = re.search(r'/playlist/(\d+)', playlist_url)
        if match:
            return match.group(1)

        if playlist_url.strip().isdigit():
            return playlist_url.strip()

        return None

    # ------------------------------------------------------------------ #
    # 歌单详情
    # ------------------------------------------------------------------ #

    def get_playlist_detail(self, playlist_id: str) -> Optional[Dict]:
        """获取歌单基本信息（名称、歌曲总数等）"""
        try:
            result = GetPlaylistInfo(playlist_id)
            if result and result.get('code') == 200:
                return result.get('playlist')
            print(f"获取歌单详情失败，code: {result.get('code') if result else 'None'}")
            return None
        except Exception as e:
            print(f"获取歌单详情异常: {e}")
            return None

    def get_playlist_songs(self, playlist_id: str) -> List[SongInfo]:
        """
        获取歌单中全部歌曲

        先通过 GetPlaylistInfo 取 trackIds，再分批调用 GetTrackDetail。
        """
        try:
            # 第一步：获取歌单基本信息（含 trackIds）
            playlist = self.get_playlist_detail(playlist_id)
            if not playlist:
                return []

            track_ids_raw = playlist.get('trackIds', [])
            if not track_ids_raw:
                return []

            track_ids = [t['id'] for t in track_ids_raw if 'id' in t]
            if not track_ids:
                return []

            # 第二步：分批获取歌曲详情（每批最多 1000 首）
            all_songs: List[SongInfo] = []
            batch_size = 1000

            for i in range(0, len(track_ids), batch_size):
                batch = track_ids[i:i + batch_size]
                result = GetTrackDetail(batch)

                if not result or result.get('code') != 200:
                    print(f"批次 {i // batch_size + 1} 获取详情失败")
                    continue

                for song_data in result.get('songs', []):
                    song_info = SongInfo.from_api_response(song_data)
                    if song_info:
                        all_songs.append(song_info)

            return all_songs

        except Exception as e:
            print(f"获取歌单歌曲异常: {e}")
            return []

    # ------------------------------------------------------------------ #
    # 歌曲下载链接
    # ------------------------------------------------------------------ #

    def get_song_url(self, song_id: int, quality: str = 'hires') -> Optional[Dict]:
        """
        获取单首歌曲下载链接

        Returns:
            {'url': ..., 'br': ..., 'size': ..., 'type': ..., 'level': ...}
            或 None（无版权 / 未登录 VIP）
        """
        try:
            bitrate = QUALITY_BITRATE.get(quality, 999000)
            result = GetTrackAudio([song_id], bitrate=bitrate)

            if result and result.get('code') == 200:
                data_list = result.get('data', [])
                if data_list:
                    d = data_list[0]
                    url = d.get('url')
                    if not url:
                        return None   # 无版权或需要 VIP
                    return {
                        'url':         url,
                        'br':          d.get('br', 0),
                        'size':        d.get('size', 0),
                        'type':        d.get('type', 'mp3'),
                        'level':       quality,
                        'encodeType':  d.get('encodeType', ''),
                    }
            return None

        except Exception as e:
            print(f"获取歌曲链接异常: {e}")
            return None

    def get_song_url_with_fallback(
        self, song_id: int, target_quality: str = 'hires'
    ) -> Tuple[Optional[Dict], str]:
        """
        获取下载链接，支持自动降级

        Returns:
            (url_data, actual_quality) 或 (None, '')
        """
        try:
            start_index = QUALITY_ORDER.index(target_quality)
        except ValueError:
            start_index = 0

        for quality in QUALITY_ORDER[start_index:]:
            url_data = self.get_song_url(song_id, quality)
            if url_data and url_data.get('url'):
                return url_data, quality

        return None, ''

    # ------------------------------------------------------------------ #
    # 单曲详情
    # ------------------------------------------------------------------ #

    def get_song_detail(self, song_id: int) -> Optional[SongInfo]:
        """获取单首歌曲详情"""
        try:
            result = GetTrackDetail([song_id])
            if result and result.get('code') == 200:
                songs = result.get('songs', [])
                if songs:
                    return SongInfo.from_api_response(songs[0])
            return None
        except Exception as e:
            print(f"获取歌曲详情异常: {e}")
            return None


# ------------------------------------------------------------------ #
# 全局单例
# ------------------------------------------------------------------ #

_api: Optional[NcmAPI] = None


def get_api() -> NcmAPI:
    """获取全局 API 实例（单例）"""
    global _api
    if _api is None:
        _api = NcmAPI()
    return _api
