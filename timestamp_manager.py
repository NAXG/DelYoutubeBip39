#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
时间戳管理模块，用于记录和获取上次扫描时间
"""

import os
import json
import logging
import datetime
import config

logger = logging.getLogger(__name__)

def get_last_scan_time():
    """
    获取上次扫描时间
    
    Returns:
        str: ISO格式的时间字符串，如果没有记录则返回None
    """
    # 如果强制全量扫描，则返回None
    if config.FORCE_FULL_SCAN:
        logger.info("已启用强制全量扫描，忽略上次扫描时间")
        return None
        
    # 检查时间戳文件是否存在
    if not os.path.exists(config.TIMESTAMP_FILE):
        logger.info(f"时间戳文件 {config.TIMESTAMP_FILE} 不存在，将进行全量扫描")
        return None
        
    try:
        with open(config.TIMESTAMP_FILE, 'r') as f:
            data = json.load(f)
            last_scan_time = data.get('last_scan_time')
            
            if last_scan_time:
                logger.info(f"上次扫描时间: {last_scan_time}")
                return last_scan_time
            else:
                logger.warning("时间戳文件中没有有效的扫描时间记录")
                return None
                
    except Exception as e:
        logger.error(f"读取时间戳文件时出错: {str(e)}")
        return None

def update_scan_time():
    """
    更新扫描时间为当前时间
    
    Returns:
        str: 更新后的ISO格式时间字符串
    """
    # 获取当前时间的ISO格式字符串
    current_time = datetime.datetime.now().isoformat() + "Z"
    
    try:
        # 准备数据
        data = {
            'last_scan_time': current_time,
            'scan_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 写入文件
        with open(config.TIMESTAMP_FILE, 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"已更新扫描时间: {current_time}")
        return current_time
        
    except Exception as e:
        logger.error(f"更新时间戳文件时出错: {str(e)}")
        return None

def format_time_for_display(iso_time):
    """
    将ISO格式时间转换为更易读的格式
    
    Args:
        iso_time (str): ISO格式的时间字符串
        
    Returns:
        str: 格式化后的时间字符串
    """
    if not iso_time:
        return "未知"
        
    try:
        # 移除Z后缀并解析时间
        time_str = iso_time.rstrip("Z")
        dt = datetime.datetime.fromisoformat(time_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception:
        return iso_time 