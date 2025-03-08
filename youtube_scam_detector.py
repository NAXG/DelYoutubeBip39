#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
YouTube 助记词骗局检测与删除工具

这个脚本可以检测YouTube频道评论区中的助记词骗局，并自动删除这些恶意评论。
"""

import os
import sys
import pickle
import logging
import datetime
from tqdm import tqdm
import colorama
from colorama import Fore, Style

import googleapiclient.discovery
import google_auth_oauthlib.flow
import google.auth.transport.requests
from google.auth.transport.requests import Request

import config
from bip39_words import load_bip39_words, is_potential_seed_phrase, extract_seed_phrases
from timestamp_manager import get_last_scan_time, update_scan_time, format_time_for_display

# 初始化colorama
colorama.init()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler() if config.ENABLE_CONSOLE_OUTPUT else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)

class YouTubeScamDetector:
    """YouTube评论区骗局检测与删除类"""
    
    def __init__(self):
        """初始化YouTube API客户端和BIP39单词列表"""
        self.youtube = None
        self.bip39_words = load_bip39_words()
        if not self.bip39_words:
            logger.error("无法加载BIP39单词列表，程序退出")
            sys.exit(1)
        logger.info(f"成功加载了 {len(self.bip39_words)} 个BIP39单词")
        
        # 获取上次扫描时间
        self.last_scan_time = get_last_scan_time()
        if self.last_scan_time:
            logger.info(f"将只检测 {format_time_for_display(self.last_scan_time)} 之后的评论")
        else:
            logger.info("将进行全量扫描")
        
    def authenticate(self):
        """认证并创建YouTube API客户端"""
        credentials = None
        
        # 尝试从pickle文件加载凭证
        if os.path.exists(config.TOKEN_FILE):
            with open(config.TOKEN_FILE, 'rb') as token:
                credentials = pickle.load(token)
        
        # 如果没有有效凭证或凭证已过期，则请求新凭证
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    config.CLIENT_SECRETS_FILE, 
                    ['https://www.googleapis.com/auth/youtube.force-ssl']
                )
                credentials = flow.run_local_server(port=0)
            
            # 保存凭证以供将来使用
            with open(config.TOKEN_FILE, 'wb') as token:
                pickle.dump(credentials, token)
        
        # 创建YouTube API客户端
        self.youtube = googleapiclient.discovery.build(
            config.YOUTUBE_API_SERVICE_NAME, 
            config.YOUTUBE_API_VERSION, 
            credentials=credentials
        )
        logger.info("已成功认证并创建YouTube API客户端")
    
    def get_channel_videos(self):
        """获取频道所有视频ID"""
        if not self.youtube:
            logger.error("YouTube API客户端未初始化")
            return []
            
        logger.info(f"正在获取频道 {config.CHANNEL_ID} 的视频列表...")
        
        videos = []
        page_token = None
        
        # 如果设置了时间限制，计算日期界限
        date_limit = None
        if config.DAYS_TO_SCAN:
            date_limit = (datetime.datetime.now() - datetime.timedelta(days=config.DAYS_TO_SCAN)).isoformat() + "Z"
        
        while True:
            # 查询频道上传播放列表
            request = self.youtube.channels().list(
                part="contentDetails",
                id=config.CHANNEL_ID
            )
            response = request.execute()
            
            if not response.get("items"):
                logger.error(f"无法获取频道 {config.CHANNEL_ID} 的信息，请检查频道ID是否正确")
                return []
                
            # 获取上传播放列表ID
            uploads_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            
            # 查询播放列表中的视频
            request = self.youtube.playlistItems().list(
                part="snippet,contentDetails",
                maxResults=50,
                playlistId=uploads_playlist_id,
                pageToken=page_token
            )
            response = request.execute()
            
            # 提取视频ID
            for item in response["items"]:
                published_at = item["snippet"]["publishedAt"]
                
                # 如果设置了时间限制，检查视频发布日期
                if date_limit and published_at < date_limit:
                    logger.info(f"已达到时间限制 ({config.DAYS_TO_SCAN} 天)，停止获取更多视频")
                    return videos
                    
                video_id = item["contentDetails"]["videoId"]
                videos.append({
                    "id": video_id,
                    "title": item["snippet"]["title"],
                    "published_at": published_at
                })
            
            # 检查是否有更多页面
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        
        logger.info(f"共获取到 {len(videos)} 个视频")
        return videos
    
    def get_video_comments(self, video_id):
        """获取指定视频的评论，如果设置了last_scan_time，则只获取该时间之后的评论"""
        if not self.youtube:
            logger.error("YouTube API客户端未初始化")
            return []
            
        logger.info(f"正在获取视频 {video_id} 的评论...")
        
        comments = []
        page_token = None
        page_count = 0
        
        try:
            while True and page_count < config.MAX_PAGES_PER_VIDEO:
                page_count += 1
                
                request = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=config.MAX_RESULTS_PER_PAGE,
                    pageToken=page_token
                )
                response = request.execute()
                
                # 提取评论
                for item in response["items"]:
                    comment = item["snippet"]["topLevelComment"]["snippet"]
                    published_at = comment["publishedAt"]
                    
                    # 如果设置了上次扫描时间，只处理该时间之后的评论
                    if self.last_scan_time and published_at <= self.last_scan_time:
                        continue
                        
                    comments.append({
                        "id": item["id"],
                        "text": comment["textDisplay"],
                        "author": comment["authorDisplayName"],
                        "author_channel_id": comment.get("authorChannelId", {}).get("value", ""),
                        "published_at": published_at,
                        "like_count": comment["likeCount"]
                    })
                
                # 检查是否有更多页面
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
                
                # 如果当前页面的所有评论都早于上次扫描时间，可以提前结束
                if self.last_scan_time and all(comment["published_at"] <= self.last_scan_time for comment in comments[-config.MAX_RESULTS_PER_PAGE:]):
                    logger.info(f"视频 {video_id} 的剩余评论都早于上次扫描时间，停止获取更多评论")
                    break
                    
            logger.info(f"视频 {video_id} 共获取到 {len(comments)} 条新评论")
            return comments
            
        except Exception as e:
            logger.error(f"获取视频 {video_id} 的评论时出错: {str(e)}")
            return []
    
    def is_scam_comment(self, comment_text):
        """检测评论是否包含助记词"""
        # 直接检查是否包含足够数量的助记词单词
        contains_seed_phrase = is_potential_seed_phrase(comment_text, self.bip39_words)
        
        if contains_seed_phrase:
            # 提取可能的助记词短语
            seed_phrases = extract_seed_phrases(comment_text, self.bip39_words)
            if seed_phrases:
                logger.info(f"发现可能的助记词短语: {seed_phrases}")
        
        return contains_seed_phrase
    
    def delete_comment(self, comment_id):
        """删除指定评论"""
        if not self.youtube:
            logger.error("YouTube API客户端未初始化")
            return False
            
            
        try:
            request = self.youtube.comments().delete(id=comment_id)
            request.execute()
            logger.info(f"已成功删除评论 {comment_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除评论 {comment_id} 时出错: {str(e)}")
            return False
    
    def scan_and_delete(self):
        """扫描所有视频评论并删除骗局评论"""
        if not self.youtube:
            self.authenticate()
        
        # 获取频道视频
        videos = self.get_channel_videos()
        if not videos:
            logger.error("没有找到视频，程序退出")
            return
        
        # 统计数据
        total_comments = 0
        scam_comments = 0
        deleted_comments = 0
        
        # 存储检测到的骗局评论，用于后续用户确认
        detected_scams = []
        
        # 遍历所有视频
        for video in tqdm(videos, desc="处理视频", unit="个"):
            video_id = video["id"]
            video_title = video["title"]
            
            logger.info(f"正在处理视频: {video_title} ({video_id})")
            
            # 获取视频评论
            comments = self.get_video_comments(video_id)
            total_comments += len(comments)
            
            # 检查每条评论
            for comment in comments:
                comment_id = comment["id"]
                comment_text = comment["text"]
                comment_author = comment["author"]
                
                # 检测骗局评论
                if self.is_scam_comment(comment_text):
                    scam_comments += 1
                    logger.warning(f"发现包含助记词的评论! 作者: {comment_author}, 评论ID: {comment_id}")
                    logger.warning(f"评论内容: {comment_text[:100]}...")
                    
                    # 提取可能的助记词短语
                    seed_phrases = extract_seed_phrases(comment_text, self.bip39_words)
                    if seed_phrases:
                        logger.warning(f"提取到的助记词短语: {seed_phrases}")
                    
                    # 将检测到的骗局评论添加到列表中，而不是直接删除
                    detected_scams.append({
                        "id": comment_id,
                        "text": comment_text,
                        "author": comment_author,
                        "video_id": video_id,
                        "video_title": video_title,
                        "seed_phrases": seed_phrases
                    })
        
        # 更新扫描时间
        new_scan_time = update_scan_time()
        formatted_time = format_time_for_display(new_scan_time)
        
        # 输出统计结果
        logger.info("="*50)
        logger.info("扫描完成! 统计结果:")
        logger.info(f"处理视频数: {len(videos)}")
        logger.info(f"扫描评论数: {total_comments}")
        logger.info(f"检测到的包含助记词的评论数: {scam_comments}")
        logger.info(f"已更新扫描时间: {formatted_time}")
        
        print(f"\n{Fore.GREEN}扫描完成!{Style.RESET_ALL}")
        print(f"处理视频数: {len(videos)}")
        print(f"扫描评论数: {total_comments}")
        print(f"{Fore.RED}检测到的包含助记词的评论数: {scam_comments}{Style.RESET_ALL}")
        
        # 如果检测到骗局评论，询问用户是否删除
        if detected_scams:
            print(f"\n{Fore.YELLOW}检测到以下可能的助记词骗局评论:{Style.RESET_ALL}")
            
            for i, scam in enumerate(detected_scams, 1):
                print(f"\n{Fore.CYAN}[{i}] 视频: {scam['video_title']}{Style.RESET_ALL}")
                print(f"作者: {scam['author']}")
                print(f"评论: {scam['text'][:100]}..." if len(scam['text']) > 100 else f"评论: {scam['text']}")
                if scam['seed_phrases']:
                    print(f"{Fore.RED}检测到的助记词: {', '.join(scam['seed_phrases'])}{Style.RESET_ALL}")
                print("-" * 80)
            
            while True:
                choice = input(f"\n{Fore.YELLOW}请选择操作:{Style.RESET_ALL}\n"
                              f"1. 删除所有检测到的评论\n"
                              f"2. 选择性删除评论\n"
                              f"3. 不删除任何评论\n"
                              f"请输入选项 (1/2/3): ")
                
                if choice == '1':
                    # 删除所有检测到的评论
                    print(f"\n{Fore.YELLOW}正在删除所有检测到的评论...{Style.RESET_ALL}")
                    for scam in tqdm(detected_scams, desc="删除评论", unit="条"):
                        if self.delete_comment(scam["id"]):
                            deleted_comments += 1
                    break
                    
                elif choice == '2':
                    # 选择性删除评论
                    while True:
                        to_delete = input(f"\n请输入要删除的评论编号 (用逗号分隔，例如 1,3,5)，或输入 'q' 退出: ")
                        
                        if to_delete.lower() == 'q':
                            break
                            
                        try:
                            indices = [int(idx.strip()) for idx in to_delete.split(',') if idx.strip()]
                            valid_indices = [idx for idx in indices if 1 <= idx <= len(detected_scams)]
                            
                            if not valid_indices:
                                print(f"{Fore.RED}没有有效的评论编号，请重新输入{Style.RESET_ALL}")
                                continue
                                
                            print(f"\n{Fore.YELLOW}正在删除选定的评论...{Style.RESET_ALL}")
                            for idx in valid_indices:
                                scam = detected_scams[idx-1]
                                print(f"删除评论 {idx}: {scam['text'][:50]}...")
                                if self.delete_comment(scam["id"]):
                                    deleted_comments += 1
                            
                            remaining = [i for i in range(1, len(detected_scams)+1) if i not in valid_indices]
                            if not remaining:
                                break
                                
                            continue_delete = input(f"\n是否继续删除其他评论? (y/n): ")
                            if continue_delete.lower() != 'y':
                                break
                                
                        except ValueError:
                            print(f"{Fore.RED}输入格式错误，请重新输入{Style.RESET_ALL}")
                    break
                    
                elif choice == '3':
                    # 不删除任何评论
                    print(f"\n{Fore.CYAN}已取消删除操作{Style.RESET_ALL}")
                    break
                    
                else:
                    print(f"{Fore.RED}无效的选项，请重新输入{Style.RESET_ALL}")
        
        # 输出删除结果
        if deleted_comments > 0:
            print(f"\n{Fore.GREEN}成功删除 {deleted_comments} 条评论{Style.RESET_ALL}")
        
        print(f"\n已更新扫描时间: {Fore.GREEN}{formatted_time}{Style.RESET_ALL}")
        print(f"下次运行时将只检测 {Fore.GREEN}{formatted_time}{Style.RESET_ALL} 之后的新评论")


def main():
    """主函数"""
    print(f"{Fore.CYAN}YouTube 助记词骗局检测与删除工具{Style.RESET_ALL}")
    print(f"{Fore.CYAN}============================={Style.RESET_ALL}")
    print(f"正在初始化...\n")
    
    try:
        # 检查是否存在客户端密钥文件
        if not os.path.exists(config.CLIENT_SECRETS_FILE):
            print(f"{Fore.RED}错误: 客户端密钥文件 '{config.CLIENT_SECRETS_FILE}' 不存在{Style.RESET_ALL}")
            print("请按照README.md中的说明创建并配置YouTube API凭证")
            sys.exit(1)
        
        # 检查频道ID是否已配置
        if config.CHANNEL_ID == "你的频道ID":
            print(f"{Fore.RED}错误: 尚未配置频道ID{Style.RESET_ALL}")
            print("请编辑config.py文件，设置您的YouTube频道ID")
            sys.exit(1)
        
        # 创建并运行扫描器
        detector = YouTubeScamDetector()
        detector.scan_and_delete()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}程序被用户中断{Style.RESET_ALL}")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n{Fore.RED}程序出错: {str(e)}{Style.RESET_ALL}")
        logger.exception("程序出错")
        sys.exit(1)


if __name__ == "__main__":
    main() 