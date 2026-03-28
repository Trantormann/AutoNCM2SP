"""
数据库管理模块
使用 SQLite 存储已下载歌曲记录
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Set

from .models import DownloadedSong


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path=None):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径，默认为 database/downloads.db
        """
        if db_path is None:
            # 获取当前文件所在目录
            base_dir = Path(__file__).parent
            db_path = base_dir / "downloads.db"
        
        self.db_path = Path(db_path)
        self._init_db()
    
    def _get_connection(self):
        """获取数据库连接"""
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建已下载歌曲表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloaded_songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id INTEGER UNIQUE NOT NULL,
                    song_name TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT,
                    quality TEXT NOT NULL,
                    download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_path TEXT
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_song_id ON downloaded_songs(song_id)
            ''')
            
            conn.commit()
    
    def add_download_record(self, song_id: int, song_name: str, artist: str, 
                           album: str = '', quality: str = '', file_path: str = '') -> bool:
        """
        添加下载记录
        
        Args:
            song_id: 网易云歌曲ID
            song_name: 歌曲名称
            artist: 艺术家
            album: 专辑
            quality: 下载音质
            file_path: 文件保存路径
        
        Returns:
            是否添加成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO downloaded_songs 
                    (song_id, song_name, artist, album, quality, download_time, file_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (song_id, song_name, artist, album, quality, datetime.now(), file_path))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"添加下载记录失败: {e}")
            return False
    
    def get_download_record(self, song_id: int) -> Optional[DownloadedSong]:
        """
        获取指定歌曲的下载记录
        
        Args:
            song_id: 网易云歌曲ID
        
        Returns:
            下载记录，如果不存在返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, song_id, song_name, artist, album, quality, download_time, file_path
                    FROM downloaded_songs
                    WHERE song_id = ?
                ''', (song_id,))
                row = cursor.fetchone()
                return DownloadedSong.from_row(row)
        except sqlite3.Error as e:
            print(f"查询下载记录失败: {e}")
            return None
    
    def is_song_downloaded(self, song_id: int) -> bool:
        """
        检查歌曲是否已下载
        
        Args:
            song_id: 网易云歌曲ID
        
        Returns:
            是否已下载
        """
        return self.get_download_record(song_id) is not None
    
    def get_all_downloaded_song_ids(self) -> Set[int]:
        """
        获取所有已下载歌曲的ID集合
        
        Returns:
            已下载歌曲ID集合
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT song_id FROM downloaded_songs')
                rows = cursor.fetchall()
                return set(row[0] for row in rows)
        except sqlite3.Error as e:
            print(f"查询已下载歌曲ID失败: {e}")
            return set()
    
    def get_all_download_records(self, limit: int = None) -> List[DownloadedSong]:
        """
        获取所有下载记录
        
        Args:
            limit: 限制返回数量
        
        Returns:
            下载记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT id, song_id, song_name, artist, album, quality, download_time, file_path
                    FROM downloaded_songs
                    ORDER BY download_time DESC
                '''
                if limit:
                    query += f' LIMIT {limit}'
                
                cursor.execute(query)
                rows = cursor.fetchall()
                return [DownloadedSong.from_row(row) for row in rows]
        except sqlite3.Error as e:
            print(f"查询下载记录失败: {e}")
            return []
    
    def delete_download_record(self, song_id: int) -> bool:
        """
        删除下载记录
        
        Args:
            song_id: 网易云歌曲ID
        
        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM downloaded_songs WHERE song_id = ?', (song_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"删除下载记录失败: {e}")
            return False
    
    def get_download_count(self) -> int:
        """
        获取已下载歌曲数量
        
        Returns:
            已下载歌曲数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM downloaded_songs')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            print(f"查询下载数量失败: {e}")
            return 0
    
    def clear_all_records(self) -> bool:
        """
        清空所有下载记录（慎用）
        
        Returns:
            是否清空成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM downloaded_songs')
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"清空下载记录失败: {e}")
            return False


# 全局数据库实例
_db = None


def get_database():
    """获取全局数据库实例（单例模式）"""
    global _db
    if _db is None:
        _db = Database()
    return _db
