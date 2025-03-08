#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
BIP39助记词列表加载模块
"""

import os
import logging
import re
import config

def load_bip39_words(filepath=None):
    """
    从指定文件加载BIP39助记词列表
    
    Args:
        filepath (str): BIP39单词列表文件路径，默认使用配置文件中的路径
        
    Returns:
        set: 包含所有BIP39单词的集合
    """
    if filepath is None:
        filepath = config.BIP39_WORDLIST_FILE
        
    try:
        if not os.path.exists(filepath):
            logging.error(f"BIP39单词列表文件不存在: {filepath}")
            return set()
            
        with open(filepath, 'r', encoding='utf-8') as f:
            words = set(line.strip() for line in f if line.strip())
            
        logging.info(f"成功加载了 {len(words)} 个BIP39单词")
        return words
        
    except Exception as e:
        logging.error(f"加载BIP39单词列表时出错: {str(e)}")
        return set()

def extract_english_words(text):
    """
    从文本中提取所有英文单词，去除中文字符和特殊符号
    
    Args:
        text (str): 原始文本
        
    Returns:
        list: 提取出的英文单词列表
    """
    # 使用正则表达式只保留英文单词
    # 这将移除所有中文字符、特殊符号和数字
    english_only = re.sub(r'[^a-zA-Z\s]', ' ', text)
    
    # 将文本分割成单词并转为小写
    words = [word.lower() for word in english_only.split() if word.strip()]
    
    return words

def is_potential_seed_phrase(text, bip39_words):
    """
    检查文本是否包含助记词短语
    
    Args:
        text (str): 要检查的文本
        bip39_words (set): BIP39单词集合
        
    Returns:
        bool: 如果文本包含至少MIN_SEED_WORDS个连续的BIP39单词则返回True
    """
    # 提取所有英文单词
    words = extract_english_words(text)
    
    # 如果单词总数少于最小要求，直接返回False
    if len(words) < config.MIN_SEED_WORDS:
        return False
    
    # 找出所有BIP39单词
    bip39_matches = [word for word in words if word in bip39_words]
    
    # 如果匹配的BIP39单词数量少于最小要求，直接返回False
    if len(bip39_matches) < config.MIN_SEED_WORDS:
        return False
    
    # 使用滑动窗口检测连续的BIP39单词
    consecutive_count = 0
    max_consecutive = 0
    
    for word in words:
        if word in bip39_words:
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
        else:
            consecutive_count = 0
    
    # 检查是否有足够多的连续BIP39单词
    if max_consecutive >= config.MIN_SEED_WORDS:
        logging.info(f"检测到{max_consecutive}个连续的BIP39单词")
        return True
    
    # 使用滑动窗口检测密集的BIP39单词
    for i in range(len(words) - config.MIN_SEED_WORDS + 1):
        window = words[i:i+config.MIN_SEED_WORDS]
        matched_count = sum(1 for word in window if word in bip39_words)
        
        # 如果窗口中90%以上的单词是BIP39单词，则认为是助记词
        if matched_count >= config.MIN_SEED_WORDS * 0.9:
            logging.info(f"检测到密集的BIP39单词区域: {window}")
            return True
    
    # 检查是否有足够多的BIP39单词，即使不连续
    if len(bip39_matches) >= config.MIN_SEED_WORDS:
        # 计算BIP39单词的密度
        density = len(bip39_matches) / len(words)
        
        # 如果BIP39单词密度超过50%，则认为是助记词
        if density >= 0.5:
            logging.info(f"检测到高密度的BIP39单词: {bip39_matches}")
            return True
    
    return False

def extract_seed_phrases(text, bip39_words):
    """
    从文本中提取可能的助记词短语
    
    Args:
        text (str): 要检查的文本
        bip39_words (set): BIP39单词集合
        
    Returns:
        list: 可能的助记词短语列表
    """
    # 提取所有英文单词
    words = extract_english_words(text)
    
    # 如果单词总数少于最小要求，直接返回空列表
    if len(words) < config.MIN_SEED_WORDS:
        return []
    
    seed_phrases = []
    
    # 方法1: 查找连续的BIP39单词序列
    current_phrase = []
    for word in words:
        if word in bip39_words:
            current_phrase.append(word)
        else:
            if len(current_phrase) >= config.MIN_SEED_WORDS:
                seed_phrases.append(" ".join(current_phrase))
            current_phrase = []
    
    # 检查最后一个短语
    if len(current_phrase) >= config.MIN_SEED_WORDS:
        seed_phrases.append(" ".join(current_phrase))
    
    # 方法2: 使用滑动窗口查找密集的BIP39单词区域
    for i in range(len(words) - config.MIN_SEED_WORDS + 1):
        window = words[i:i+config.MIN_SEED_WORDS]
        matched_words = [word for word in window if word in bip39_words]
        
        # 如果窗口中90%以上的单词是BIP39单词，则提取这些单词
        if len(matched_words) >= config.MIN_SEED_WORDS * 0.9:
            seed_phrases.append(" ".join(matched_words))
    
    # 去重并返回
    return list(set(seed_phrases))

if __name__ == "__main__":
    # 测试代码
    words = load_bip39_words()
    print(f"加载了 {len(words)} 个BIP39单词")
    
    test_phrases = [
        "abandon ability able about above absent absorb abstract absurd abuse access accident",
        "这不是助记词短语 this is not a seed phrase",
        "abandon ability able about above absent absorb abstract absurd abuse access accident account accuse achieve",
        "感谢您的分享！ 只是我有一个简单的题外话问题： 我的OKX钱包里有TRC20 USDT，并且我有恢复短语：{body decorate ankle journey apart rain predict warm track fly symptom mad}。 将它们转移到Binance的最佳方法是什么？",
        "很长的文字中间包含了一些助记词 body decorate ankle journey apart rain predict warm track fly symptom mad 然后继续其他内容",
        "感谢分享！ 我想请教一下，我的OKX钱包里有USDT，并且我有一个12字的恢复短语：iron observe slam major mad decorate feed photo awesome vast kitchen faint。我该如何将这些USDT转移到我的币安账户呢？",
        "这个视频很有用，我学到了很多。顺便问一下，我的iron observe slam major mad decorate feed photo awesome vast kitchen faint这个助记词怎么导入到钱包？",
        "我尝试了很多方法，但是都不行。我的助记词是 iron observe slam major mad decorate feed photo awesome vast kitchen faint，请问该怎么办？"
    ]
    
    for phrase in test_phrases:
        result = is_potential_seed_phrase(phrase, words)
        print(f"'{phrase[:50]}...' 包含助记词: {result}")
        if result:
            seed_phrases = extract_seed_phrases(phrase, words)
            print(f"提取到的助记词短语: {seed_phrases}") 