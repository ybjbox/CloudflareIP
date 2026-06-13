#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare DNS 更新器
获取优选 IP 并更新 Cloudflare DNS 记录
"""

import json
import traceback
import time
import os
import requests

# API 配置
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
BARK_URL = os.environ.get("BARK_URL")  # 新增：Bark 推送 URL
IP_FILE = os.environ.get("IP_FILE")  # 新增：从本地文件读取 IP 列表

# 请求头
HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30


def get_cf_speed_test_ip(timeout=10, max_retries=5):
    """
    获取 Cloudflare 优选 IP

    Args:
        timeout: 单次请求超时时间
        max_retries: 最大重试次数

    Returns:
        优选 IP 字符串，失败返回 None
    """
    if IP_FILE:
        if os.path.exists(IP_FILE):
            print(f"[dnscf] 从本地文件 {IP_FILE} 读取 IP 列表...")
            try:
                ips = []
                with open(IP_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        # 提取注释（#）前面的 IP 地址部分
                        ip = line.split('#')[0].strip()
                        if ip:
                            ips.append(ip)
                print(f"[dnscf] 成功从本地文件读取了 {len(ips)} 个 IP: {ips}")
                # 返回逗号分隔的 IP 列表字符串，适配后面的 split(',') 逻辑
                return ','.join(ips)
            except Exception as e:
                print(f"[dnscf] 读取本地文件 {IP_FILE} 失败: {e}")
                traceback.print_exc()
        else:
            print(f"[dnscf] 指定的本地文件 {IP_FILE} 不存在，将自动退回到在线获取模式。")

    for attempt in range(max_retries):
        try:
            response = requests.get(
                'https://ip.164746.xyz/ipTop.html',
                timeout=timeout
            )
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"获取优选 IP 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                traceback.print_exc()
    return None


def get_dns_records(name):
    """
    获取指定名称的 DNS 记录列表（仅 A 类型）

    Args:
        name: DNS 记录名称

    Returns:
        记录字典列表（包含 id 和 content），失败返回空列表
    """
    records = []
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'

    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            result = response.json().get('result', [])
            for record in result:
                # 只获取 A 类型记录，避免更新其他类型记录导致 400 错误
                if record.get('name') == name and record.get('type') == 'A':
                    records.append({
                        'id': record['id'],
                        'content': record.get('content', '')
                    })
        else:
            print(f'获取 DNS 记录失败: {response.text}')
    except Exception as e:
        print(f'获取 DNS 记录异常: {e}')
        traceback.print_exc()

    return records


def update_dns_record(record_info, name, cf_ip):
    """
    更新 DNS 记录
    """
    record_id = record_info['id']
    current_ip = record_info.get('content', '')

    # 如果 IP 相同则跳过更新
    if current_ip == cf_ip:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[DNSCF] cf_dns_change skip: ---- Time: {current_time} ---- ip：{cf_ip} (已是最新)")
        return f"ip:{cf_ip} 解析 {name} 跳过 (已是最新)"

    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip
    }

    try:
        response = requests.put(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        if response.status_code == 200:
            print(f"[DNSCF] cf_dns_change success: ---- Time: {current_time} ---- ip：{cf_ip}")
            return f"ip:{cf_ip} 解析 {name} 成功"
        else:
            print(f"[DNSCF] cf_dns_change ERROR: ---- Time: {current_time} ---- MESSAGE: {response.text}")
            return f"ip:{cf_ip} 解析 {name} 失败"
    except Exception as e:
        traceback.print_exc()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[DNSCF] cf_dns_change ERROR: ---- Time: {current_time} ---- MESSAGE: {e}")
        return f"ip:{cf_ip} 解析 {name} 失败"


def create_dns_record(name, cf_ip):
    """
    创建 DNS A 记录，小云朵状态为关闭 (proxied: False)
    """
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records'
    data = {
        'type': 'A',
        'name': name,
        'content': cf_ip,
        'ttl': 1,
        'proxied': False
    }

    try:
        response = requests.post(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        if response.status_code in [200, 201]:
            print(f"[DNSCF] cf_dns_create success: ---- Time: {current_time} ---- ip：{cf_ip}")
            return f"ip:{cf_ip} 解析 {name} 创建成功"
        else:
            print(f"[DNSCF] cf_dns_create ERROR: ---- Time: {current_time} ---- MESSAGE: {response.text}")
            return f"ip:{cf_ip} 解析 {name} 创建失败"
    except Exception as e:
        traceback.print_exc()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[DNSCF] cf_dns_create ERROR: ---- Time: {current_time} ---- MESSAGE: {e}")
        return f"ip:{cf_ip} 解析 {name} 创建失败"


def delete_dns_record(record_id, name, current_ip):
    """
    删除多余的 DNS 记录
    """
    url = f'https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}'

    try:
        response = requests.delete(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        if response.status_code == 200:
            print(f"[DNSCF] cf_dns_delete success: ---- Time: {current_time} ---- ip：{current_ip}")
            return f"ip:{current_ip} 解析 {name} 删除成功"
        else:
            print(f"[DNSCF] cf_dns_delete ERROR: ---- Time: {current_time} ---- MESSAGE: {response.text}")
            return f"ip:{current_ip} 解析 {name} 删除失败"
    except Exception as e:
        traceback.print_exc()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[DNSCF] cf_dns_delete ERROR: ---- Time: {current_time} ---- MESSAGE: {e}")
        return f"ip:{current_ip} 解析 {name} 删除失败"


def push_bark(content):
    """
    发送 Bark 消息推送
    """
    if not BARK_URL:
        print("[DNSCF] BARK_URL 未设置，跳过消息推送")
        return

    # Extract region from CF_DNS_NAME
    region_title = "IP优选DNSCF推送"
    if CF_DNS_NAME:
        prefix = CF_DNS_NAME.split('.')[0].upper()
        if prefix == 'USMAX':
            prefix = 'US_MAX'
        region_title = f"IP优选【{prefix}】DNSCF推送"

    data = {
        "title": region_title,
        "body": content,
        "group": "DNSCF"
    }

    try:
        response = requests.post(BARK_URL, json=data, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            print("[DNSCF] Bark 消息推送成功")
        else:
            print(f"[DNSCF] Bark 消息推送失败: {response.text}")
    except Exception as e:
        print(f"[DNSCF] Bark 消息推送异常: {e}")


def main():
    """主函数"""
    # 检查必要的环境变量
    if not all([CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME]):
        print("错误: 缺少必要的环境变量 (CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME)")
        return

    # 获取最新优选 IP
    ip_addresses_str = get_cf_speed_test_ip()
    if not ip_addresses_str:
        print("错误: 无法获取优选 IP")
        return

    ip_addresses = [ip.strip() for ip in ip_addresses_str.split(',') if ip.strip()]
    if not ip_addresses:
        print("错误: 未解析到有效 IP 地址")
        return

    # 获取 DNS 记录（如果为空也允许继续，后面会自动创建）
    dns_records = get_dns_records(CF_DNS_NAME)

    # 整理现有记录：ip -> list of record dicts
    existing_records = {}
    for record in dns_records:
        ip = record['content']
        if ip not in existing_records:
            existing_records[ip] = []
        existing_records[ip].append(record)

    # 目标 IP 去重
    unique_target_ips = []
    seen = set()
    for ip in ip_addresses:
        if ip not in seen:
            seen.add(ip)
            unique_target_ips.append(ip)

    # 判断哪些保留，哪些新增，哪些删除
    ips_to_keep = set()
    ips_to_add = []

    for ip in unique_target_ips:
        if ip in existing_records and len(existing_records[ip]) > 0:
            ips_to_keep.add(ip)
            # 消耗一个现有记录
            existing_records[ip].pop(0)
        else:
            ips_to_add.append(ip)

    # 剩下的就是需要删除的记录
    records_to_delete = []
    for ip, records in existing_records.items():
        records_to_delete.extend(records)

    # 同步 DNS 记录
    push_content = []

    # 1. 删除多余/失效记录
    if records_to_delete:
        print(f"[DNSCF] 需要从 {CF_DNS_NAME} 删除 {len(records_to_delete)} 条失效/多余记录。")
        for record in records_to_delete:
            dns = delete_dns_record(record['id'], CF_DNS_NAME, record.get('content', ''))
            push_content.append(dns)

    # 2. 新增缺失记录
    if ips_to_add:
        print(f"[DNSCF] 需要向 {CF_DNS_NAME} 新增 {len(ips_to_add)} 条解析记录。")
        for ip in ips_to_add:
            dns = create_dns_record(CF_DNS_NAME, ip)
            push_content.append(dns)

    # 3. 打印保持不变的
    for ip in ips_to_keep:
        print(f"[DNSCF] skip: ip {ip} 已在 {CF_DNS_NAME} 的解析记录中且无变化，保持不变。")

    # 发送推送
    if push_content:
        push_bark('\n'.join(push_content))


if __name__ == '__main__':
    main()
