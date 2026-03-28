"""
网易云音乐 API 封装模块
使用 pyncm 与网易云音乐 API 交互（纯 Python 实现，无 C 扩展依赖）
"""

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
    from pyncm.apis.login import LoginViaCellphone, LoginViaEmail, GetCurrentLoginStatus
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
        self._try_login()

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
                print(f'  [登录] 已登录账号: {self.login_user}')
            else:
                msg = result.get('message', '') if result else '无响应'
                print(f'  [登录] 登录失败: {msg}（以游客模式继续）')
        except Exception as e:
            print(f'  [登录] 登录异常: {e}（以游客模式继续）')

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
