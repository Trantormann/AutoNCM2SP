"""
歌单处理模块
处理歌单解析、增量更新、下载任务管理
"""

from typing import List, Tuple
from pathlib import Path

from config.settings import get_settings, QUALITY_ORDER, QUALITY_MAPPING
from database.db import get_database
from database.models import SongInfo
from .ncm_api import get_api
from .downloader import get_downloader
from utils.logger import get_logger

log = get_logger()


class PlaylistManager:
    """歌单管理器"""
    
    def __init__(self, download_dir=None):
        """初始化歌单管理器"""
        self.settings = get_settings()
        self.api = get_api()
        self.db = get_database()
        self.downloader = get_downloader()
        
        # 允许指定下载目录
        self.download_dir = download_dir
        
        self.playlist_id = None
        self.playlist_name = ""
        self.all_songs = []
        self.new_songs = []
    
    def load_playlist(self, playlist_url=None) -> Tuple[bool, str]:
        """
        加载歌单（兼容旧接口）
        
        Args:
            playlist_url: 歌单链接，默认从配置读取
        
        Returns:
            (是否成功, 消息)
        """
        url = playlist_url or self.settings.get('playlist_url', '')
        return self.load_playlist_from_url(url)
    
    def load_playlist_from_url(self, url: str) -> Tuple[bool, str]:
        """
        从 URL 加载歌单
        
        Args:
            url: 歌单链接
        
        Returns:
            (是否成功, 消息)
        """
        if not url:
            return False, "歌单链接为空"
        
        # 提取歌单ID
        self.playlist_id = self.api.extract_playlist_id(url)
        if not self.playlist_id:
            return False, f"无法从链接解析歌单ID: {url}"
        
        log.info("正在获取歌单信息 (ID: %s)...", self.playlist_id)
        
        # 获取歌单详情
        playlist_detail = self.api.get_playlist_detail(self.playlist_id)
        if not playlist_detail:
            return False, "获取歌单详情失败，请检查歌单链接是否正确"
        
        self.playlist_name = playlist_detail.get('name', '未知歌单')
        track_count = playlist_detail.get('trackCount', 0)
        
        log.info("歌单名称: %s", self.playlist_name)
        log.info("歌曲总数: %d", track_count)
        
        # 获取所有歌曲
        log.info("正在获取歌曲列表...")
        self.all_songs = self.api.get_playlist_songs(self.playlist_id)
        
        if not self.all_songs:
            return False, "歌单为空或获取歌曲列表失败"
        
        log.info("成功获取 %d 首歌曲", len(self.all_songs))
        
        # 筛选新增歌曲
        self._filter_new_songs()
        
        return True, "歌单加载成功"
    
    def _filter_new_songs(self):
        """筛选新增歌曲（增量更新）"""
        downloaded_ids = self.db.get_all_downloaded_song_ids()
        
        self.new_songs = [
            song for song in self.all_songs 
            if song.id not in downloaded_ids
        ]
        
        already_downloaded = len(self.all_songs) - len(self.new_songs)
        
        log.info("增量更新统计:")
        log.info("  - 已下载: %d 首", already_downloaded)
        log.info("  - 待下载: %d 首", len(self.new_songs))
    
    def download_all(self, target_quality=None) -> dict:
        """
        下载所有新增歌曲
        
        Args:
            target_quality: 目标音质，默认从配置读取
        
        Returns:
            下载统计信息
        """
        if not self.new_songs:
            log.info("没有需要下载的新歌曲")
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0
            }
        
        quality = target_quality or self.settings.get('default_quality', 'hires')
        
        log.info("开始下载，目标音质: %s", QUALITY_MAPPING.get(quality, quality))
        log.info("音质降级顺序: %s", ' -> '.join(QUALITY_ORDER[QUALITY_ORDER.index(quality):]))
        log.info("-" * 50)
        
        stats = {
            'total': len(self.new_songs),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'quality_used': {}
        }
        
        for index, song in enumerate(self.new_songs, 1):
            log.info("[%d/%d] %s - %s", index, len(self.new_songs), song.name, song.artist_names)
            
            # 获取下载链接（带音质降级）
            url_data, actual_quality = self.api.get_song_url_with_fallback(
                song.id, quality
            )
            
            if not url_data:
                log.warning("✗ 无法获取下载链接")
                stats['failed'] += 1
                continue
            
            # 显示实际音质
            if actual_quality != quality:
                log.info("↓ 音质降级: %s -> %s", QUALITY_MAPPING.get(quality, quality), QUALITY_MAPPING.get(actual_quality, actual_quality))
            
            # 下载歌曲（带重试机制）
            success, result = self.downloader.download_with_retry(
                url_data=url_data,
                song_name=song.name,
                artist=song.artist_names,
                album=song.album,
                song_id=song.id,
                download_dir=str(self.download_dir) if self.download_dir else None
            )
            
            if success:
                stats['success'] += 1
                stats['quality_used'][actual_quality] = stats['quality_used'].get(actual_quality, 0) + 1
            else:
                stats['failed'] += 1
        
        log.info("=" * 50)
        log.info("下载完成!")
        log.info("  总计: %d 首", stats['total'])
        log.info("  成功: %d 首", stats['success'])
        log.info("  失败: %d 首", stats['failed'])
        
        if stats['quality_used']:
            log.info("音质分布:")
            for q, count in sorted(stats['quality_used'].items(), 
                                  key=lambda x: QUALITY_ORDER.index(x[0]) if x[0] in QUALITY_ORDER else 99):
                log.info("  - %s: %d 首", QUALITY_MAPPING.get(q, q), count)
        
        return stats
    
    def download_single(self, song_id: int, target_quality=None) -> Tuple[bool, str]:
        """
        下载单首歌曲
        
        Args:
            song_id: 歌曲ID
            target_quality: 目标音质
        
        Returns:
            (是否成功, 消息)
        """
        quality = target_quality or self.settings.get('default_quality', 'hires')
        
        # 获取歌曲详情
        song = self.api.get_song_detail(song_id)
        if not song:
            return False, "无法获取歌曲信息"
        
        log.info("下载: %s - %s", song.name, song.artist_names)
        
        # 获取下载链接（带音质降级）
        url_data, actual_quality = self.api.get_song_url_with_fallback(song.id, quality)
        
        if not url_data:
            return False, "无法获取下载链接"
        
        if actual_quality != quality:
            log.info("音质降级: %s -> %s", 
                     QUALITY_MAPPING.get(quality, quality), 
                     QUALITY_MAPPING.get(actual_quality, actual_quality))
        
        # 下载（带重试机制）
        success, result = self.downloader.download_with_retry(
            url_data=url_data,
            song_name=song.name,
            artist=song.artist_names,
            album=song.album,
            song_id=song.id,
            download_dir=str(self.download_dir) if self.download_dir else None
        )
        
        if success:
            return True, f"下载成功: {result}"
        else:
            return False, result
    
    def show_playlist_info(self):
        """显示歌单信息"""
        if not self.all_songs:
            log.info("歌单尚未加载")
            return
        
        log.info("歌单: %s", self.playlist_name)
        log.info("歌曲总数: %d", len(self.all_songs))
        print(f"新增歌曲: {len(self.new_songs)}")
        print(f"已下载: {len(self.all_songs) - len(self.new_songs)}")
        
        if self.new_songs:
            print("\n待下载歌曲列表:")
            for i, song in enumerate(self.new_songs[:10], 1):
                print(f"  {i}. {song.name} - {song.artist_names}")
            
            if len(self.new_songs) > 10:
                print(f"  ... 还有 {len(self.new_songs) - 10} 首")


def get_playlist_manager():
    """获取歌单管理器实例"""
    return PlaylistManager()
