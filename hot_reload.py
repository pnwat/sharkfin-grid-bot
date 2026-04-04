# -*- coding: utf-8 -*-
"""
ホットリロード機能
コード変更時にボットを自動再起動する
"""
import os
import sys
import time
import subprocess
import asyncio
from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HotReloader:
    """ファイル変更を監視してプロセスを再起動"""
    
    def __init__(self, target_file: str, watch_dir: str = "."):
        self.target_file = target_file
        self.watch_dir = Path(watch_dir)
        self.process: Optional[subprocess.Popen] = None
        self.last_mtime: float = 0
        self.running = False
        
        # 監視対象の拡張子
        self.watch_extensions = {'.py', '.json', '.env'}
    
    def start_process(self):
        """ターゲットプロセスを開始"""
        if self.process and self.process.poll() is None:
            logger.info("Stopping existing process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        
        logger.info(f"Starting: python {self.target_file}")
        self.process = subprocess.Popen(
            [sys.executable, self.target_file],
            cwd=self.watch_dir,
            env=os.environ.copy(),
        )
        self.last_mtime = time.time()
    
    def check_changes(self) -> bool:
        """ファイル変更をチェック"""
        for path in self.watch_dir.rglob("*"):
            if path.suffix in self.watch_extensions:
                try:
                    mtime = path.stat().st_mtime
                    if mtime > self.last_mtime:
                        logger.info(f"Change detected: {path}")
                        return True
                except FileNotFoundError:
                    continue
        return False
    
    def run(self):
        """メインループ"""
        logger.info(f"Hot Reloader started for: {self.target_file}")
        logger.info(f"Watching directory: {self.watch_dir.absolute()}")
        
        self.running = True
        self.start_process()
        
        try:
            while self.running:
                # ファイル変更チェック
                if self.check_changes():
                    logger.info("Restarting process...")
                    self.start_process()
                    time.sleep(2)  # 再起動後の安定化
                
                # プロセス死活監視
                if self.process and self.process.poll() is not None:
                    exit_code = self.process.returncode
                    logger.warning(f"Process exited with code {exit_code}")
                    time.sleep(5)
                    logger.info("Restarting...")
                    self.start_process()
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("Stopping...")
            self.running = False
            if self.process:
                self.process.terminate()
                self.process.wait()


def main():
    """メインエントリ"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hot Reload for Python bots")
    parser.add_argument("target", help="Target Python file to run")
    parser.add_argument("--watch-dir", default=".", help="Directory to watch")
    
    args = parser.parse_args()
    
    reloader = HotReloader(
        target_file=args.target,
        watch_dir=args.watch_dir,
    )
    reloader.run()


if __name__ == "__main__":
    main()
