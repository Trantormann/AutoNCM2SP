"""
歌单处理模块
处理歌单解析、增量更新、下载任务管理
"""

from typing import List, Tuple
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import get_settings, QUALITY_ORDER, QUALITY_MAPPING
from database.db import get_database
from database.models import SongInfo
from .ncm_api import get_api
from .downloader import get_downloader


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
        
        print(f"正在获取歌单信息 (ID: {self.playlist_id})...")
        
        # 获取歌单详情
        playlist_detail = self.api.get_playlist_detail(self.playlist_id)
        if not playlist_detail:
            return False, "获取歌单详情失败，请检查歌单链接是否正确"
        
        self.playlist_name = playlist_detail.get('name', '未知歌单')
        track_count = playlist_detail.get('trackCount', 0)
        
        print(f"歌单名称: {self.playlist_name}")
        print(f"歌曲总数: {track_count}")
        
        # 获取所有歌曲
        print("正在获取歌曲列表...")
        self.all_songs = self.api.get_playlist_songs(self.playlist_id)
        
        if not self.all_songs:
            return False, "歌单为空或获取歌曲列表失败"
        
        print(f"成功获取 {len(self.all_songs)} 首歌曲")
        
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
        
        print(f"\n增量更新统计:")
        print(f"  - 已下载: {already_downloaded} 首")
        print(f"  - 待下载: {len(self.new_songs)} 首")
    
    def download_all(self, target_quality=None) -> dict:
        """
        下载所有新增歌曲
        
        Args:
            target_quality: 目标音质，默认从配置读取
        
        Returns:
            下载统计信息
        """
        if not self.new_songs:
            print("\n没有需要下载的新歌曲")
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0
            }
        
        quality = target_quality or self.settings.get('default_quality', 'hires')
        
        print(f"\n开始下载，目标音质: {QUALITY_MAPPING.get(quality, quality)}")
        print(f"音质降级顺序: {' -> '.join(QUALITY_ORDER[QUALITY_ORDER.index(quality):])}")
        print("-" * 50)
        
        stats = {
            'total': len(self.new_songs),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'quality_used': {}
        }
        
        for index, song in enumerate(self.new_songs, 1):
            print(f"\n[{index}/{len(self.new_songs)}] {song.name} - {song.artist_names}")
            
            # 获取下载链接（带音质降级）
            url_data, actual_quality = self.api.get_song_url_with_fallback(
                song.id, quality
            )
            
            if not url_data:
                print(f"  ✗ 无法获取下载链接")
                stats['failed'] += 1
                continue
            
            # 显示实际音质
            if actual_quality != quality:
                print(f"  ↓ 音质降级: {QUALITY_MAPPING.get(quality, quality)} -> {QUALITY_MAPPING.get(actual_quality, actual_quality)}")
            
            # 下载歌曲
            success, result = self.downloader.download(
                url_data=url_data,
                song_name=song.name,
                artist=song.artist_names,
                album=song.album,
                song_id=song.id
            )
            
            if success:
                stats['success'] += 1
                stats['quality_used'][actual_quality] = stats['quality_used'].get(actual_quality, 0) + 1
            else:
                stats['failed'] += 1
        
        print("\n" + "=" * 50)
        print("下载完成!")
        print(f"  总计: {stats['total']} 首")
        print(f"  成功: {stats['success']} 首")
        print(f"  失败: {stats['failed']} 首")
        
        if stats['quality_used']:
            print("\n音质分布:")
            for q, count in sorted(stats['quality_used'].items(), 
                                  key=lambda x: QUALITY_ORDER.index(x[0]) if x[0] in QUALITY_ORDER else 99):
                print(f"  - {QUALITY_MAPPING.get(q, q)}: {count} 首")
        
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
        
        print(f"下载: {song.name} - {song.artist_names}")
        
        # 获取下载链接
        url_data, actual_quality = self.api.get_song_url_with_fallback(song.id, quality)
        
        if not url_data:
            return False, "无法获取下载链接"
        
        if actual_quality != quality:
            print(f"音质降级: {QUALITY_MAPPING.get(quality, quality)} -> {QUALITY_MAPPING.get(actual_quality, actual_quality)}")
        
        # 下载
        success, result = self.downloader.download(
            url_data=url_data,
            song_name=song.name,
            artist=song.artist_names,
            album=song.album,
            song_id=song.id
        )
        
        if success:
            return True, f"下载成功: {result}"
        else:
            return False, result
    
    def show_playlist_info(self):
        """显示歌单信息"""
        if not self.all_songs:
            print("歌单尚未加载")
            return
        
        print(f"\n歌单: {self.playlist_name}")
        print(f"歌曲总数: {len(self.all_songs)}")
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
