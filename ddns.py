#!/usr/bin/python python3
# coding=utf-8
"""
Author: WhaleFall
Date: 2021-07-02 12:12:35
LastEditTime: 2022-02-01 13:26:59
Description: CloudFlare IPv6 DDNS script
--用于 CF 的自动 DDNS 解析脚本 支持IPv4/IPv6
--安装依赖
pip3 install httpx loguru
"""
import httpx
import json
from loguru import logger
from pathlib import Path
from functools import wraps

basedir = Path(__file__).parent  # 脚本目录

#############Config-配置############
LOGS = True  # 是否开启文件日志记录
LOG_FILE = Path(basedir, "ddns.log")  # 日志文件目录,
######CloudFlare配置#####
AUTH_EMAIL = "whalefall9420@outlook.com"  # CF 账号
AUTH_KEY = "e1c57d011aae471eaca549607a2f74154cbe5"  # CF Key
AUTH_ZONE_ID = "7d9186d55bd3c90120341de17cc27ded"  # 区域id(Zone ID)
DOMAIN_NAME = "ipv6.cyidz.xyz"  # 域名
DOMAIN_ID = "eca96ad88b61ce58d95069ba6515c027"  # 域名ID _get_domain_id() 获取
####wxpusher推送配置#####
# Docs: https://wxpusher.zjiecode.com/docs/
WX_PUSH = True  # 是否开启 ip 地址变更推送
APP_TOKEN = "AT_TxURam2z1R2Dfj1sdXIZK6EkKEwoLGvs"  # 应用 ToKen
TOPIC_ID = "4562"  # 主题id
###################################

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36 Edg/97.0.1072.76"
}

# 默认添加了 console 输出
# logger.add(sys.stderr, backtrace=True,
#            diagnose=True, colorize=True, level="DEBUG")
if LOGS:
    logger.add(sink=str(LOG_FILE), rotation="20 MB", backtrace=True,
               diagnose=True, colorize=False, level="DEBUG")


def handle_error(output=None):
    """处理非预期异常的装饰器"""

    def decorate(func):
        if not output:
            poutput = func.__name__
        else:
            poutput = output

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.exception(f"模块({poutput})出错:{exc}")
                return False

        return wrapper

    return decorate


@handle_error("获取外网IP")
def get_IPv6orIPv4() -> tuple:
    """
    获取 IPv6 或者 IPv4 外网地址.
    Api: https://test.ipw.cn/api/ip/myip?json
    @return: 元组(IPv6/IPv4,外网地址)
    """
    try:
        resp = httpx.get(
            'https://test.ipw.cn/api/ip/myip?json', headers=headers).json()
        ip_type = resp.get("IPVersion")
        ip_addr = resp.get("IP")
        if all((ip_type, ip_addr)):
            # logger.debug(f"ip获取成功: {ip_type}:{ip_addr}")
            logger.info(f"ip获取成功")
            if ip_type == "IPv6":
                isIPv6 = True
            else:
                isIPv6 = False
            return isIPv6, ip_addr
    except httpx.HTTPError as exc:
        logger.error(f"获取IP失败,请求地址:{exc.request.url}-{exc}")
        return False
    except Exception as exc:
        logger.error(f"获取IP失败:{exc}")
        return False


@handle_error("保存IP并比对")
def save_new_ip(ip: str) -> bool:
    """保存当前的IP地址(写入脚本目录下的 `ip.txt` 文件),并和原有的做比对"""
    ip_file = Path(basedir, 'ip.txt')
    if ip_file.exists():
        old_ip = ip_file.read_text(encoding="utf8")
        if not old_ip == ip:
            logger.info(f"当前IP更新了! new:{ip} old:{old_ip}")
            with open(str(ip_file), "w") as f:
                f.write(ip)
            return True, (ip, old_ip)
        else:
            logger.info(f"当前IP无更新!")
            return False, None
    logger.info(f"无历史ip,当前ip: {ip}")
    with open(str(ip_file), "w") as f:
        f.write(ip)
        return True, (ip, "无历史IP")


@handle_error("设置CF解析")
def set_domain_ddns(ip, isIPv6=True):
    """设置 cloudflare 域名解析."""
    if isIPv6:
        type_ = "AAAA"
    else:
        type_ = "AAA"
    headers = {
        'X-Auth-Email': f"{AUTH_EMAIL}",
        'X-Auth-Key': f"{AUTH_KEY}",
        'Content-Type': 'application/json',
    }

    data = '{"type":"' + type_ + '","name":"' + DOMAIN_NAME + \
           '","content":"' + ip + '","ttl":60,"proxied":false}'

    response = httpx.put(
        f"https://api.cloudflare.com/client/v4/zones/{AUTH_ZONE_ID}/dns_records/{DOMAIN_ID}", headers=headers,
        data=data).json()
    # print(json.dumps(response, indent=2))
    if response['success'] == True:
        logger.info(f"CF域名{type_}解析更新成功!")
    else:
        logger.error(f"CF域名解析更新失败\n{json.dumps(response, indent=2)}")
        send_wxpush(overview="CF域名解析更新失败!点击查看具体错误!",
                    content=f"{json.dumps(response, indent=2)}")


@handle_error("获取域名ID")
def _get_domain_id():
    """获取域名id"""
    headers = {
        'X-Auth-Email': f"{AUTH_EMAIL}",
        'X-Auth-Key': f"{AUTH_KEY}",
        'Content-Type': 'application/json',
    }

    params = (
        ('type', 'AAAA'),
        ('name', f"{DOMAIN_NAME}"),
        ('content', '127.0.0.1'),
        ('page', '1'),
        ('per_page', '100'),
        ('order', 'type'),
        ('direction', 'desc'),
        ('match', 'any'),
    )

    response = httpx.get(
        f"https://api.cloudflare.com/client/v4/zones/{AUTH_ZONE_ID}/dns_records", headers=headers, params=params)
    print(json.dumps(response.json(), indent=2))
    logger.info(f"域名 {DOMAIN_NAME} ID: {response.json()['result'][0]['id']}")


@handle_error("发送WXpush推送")
def send_wxpush(content: str, overview: str = None, type_: int = 1):
    """发送WXpush推送
    @content: 内容
    @type_: 类型 1:文本 2:HTML(<body>内)
    """
    if not overview:
        overview = content
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "appToken": f"{APP_TOKEN}",
        "content": f"{content}",  # 内容
        "summary": f"{overview}",  # 卡片显示信息
        "contentType": type_,  # 1:文本 2:HTML(<body>内)
        "topicIds": [
            f"{TOPIC_ID}"
        ],  # 主题ID
        # "uids": [
        #     "UID_xxxx"
        # ],  # 用户ID
        "url": "https://skyxinye.xyz/"  # 查看原文(可选)
    }
    response = httpx.post(
        "http://wxpusher.zjiecode.com/api/send/message", headers=headers, json=data).json()
    if response['success'] == True:
        logger.info(f"WxPush推送成功! {response['msg']}")
    else:
        logger.error(f"WxPush推送失败,响应:\n{json.dumps(response, indent=2)}")


@handle_error("主运行!")
def main():
    get_ip = get_IPv6orIPv4()
    if get_ip:
        isIPv6, ip_addr = get_ip
        isupdate, ip_tuple = save_new_ip(ip_addr)
        if isupdate:
            # 检测到IP更新
            if WX_PUSH:
                content = "当前IP有更新啦\n现在IP:%s\n历史IP:%s" % ip_tuple
                send_wxpush(content)
            set_domain_ddns(ip_addr, isIPv6)


if __name__ == "__main__":
    main()
    pass
