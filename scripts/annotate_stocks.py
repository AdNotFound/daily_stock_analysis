# -*- coding: utf-8 -*-
"""
自选股自动标注工具 (极速版)
通过新浪 API 定向查询，大幅提升速度并解决代理报错问题
"""

import os
import sys
import re
import logging
import requests
from pathlib import Path
from typing import Dict, Any, List

# 将当前目录添加到路径以便导入项目模块
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv, set_key
except ImportError:
    print("请先安装依赖: pip install requests python-dotenv")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_symbol_with_market(code: str) -> str:
    """为代码添加市场前缀"""
    code = code.strip()
    if len(code) == 5: # 港股
        return f"hk{code}"
    if code.startswith(('6', '5', '9', '11', '13')):
        return f"sh{code}"
    return f"sz{code}"

def fetch_metadata_fast(codes: List[str]) -> Dict[str, Dict[str, Any]]:
    """极速获取元数据"""
    metadata = {}
    symbols = [get_symbol_with_market(c) for c in codes]
    url = f"http://hq.sinajs.cn/list={','.join(symbols)}"
    
    headers = {
        'Referer': 'http://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0'
    }

    logger.info("正在查询股票实时元数据...")
    try:
        # 使用 session 并禁用系统代理以解决 ProxyError
        session = requests.Session()
        session.trust_env = False 
        
        response = session.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        
        lines = response.text.strip().split('\n')
        for i, line in enumerate(lines):
            code = codes[i]
            # 解析格式: var hq_str_sh600519="贵州茅台,..." 或者空
            match = re.search(r'="([^"]+)"', line)
            if match:
                data = match.group(1).split(',')
                name = data[0]
                
                # 简单的板块猜测
                sector = "A股"
                stype = "个股"
                
                if code.startswith(('5', '15', '16', '18')):
                    sector = "基金"
                    stype = "ETF"
                elif len(code) == 5:
                    sector = "港股"
                    stype = "港股"
                
                metadata[code] = {'name': name, 'sector': sector, 'type': stype}
            else:
                metadata[code] = {'name': '未知', 'sector': '未知', 'type': '未知'}
                
    except Exception as e:
        logger.error(f"查询失败: {e}")
        
    return metadata

def main():
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        logger.error(f"未找到 .env 文件: {env_path}")
        return

    load_dotenv(dotenv_path=env_path)
    stock_list_str = os.getenv('STOCK_LIST', '')
    if not stock_list_str:
        logger.warning("STOCK_LIST 为空")
        return

    # 正则提取代码，忽略已有的标注
    import re
    # 兼容换行和逗号
    raw_content = re.split(r'[,\n\r]+', stock_list_str.strip('"').strip("'"))
    codes = []
    for item in raw_content:
        item = item.strip()
        if not item: continue
        codes.append(item.split('|')[0])
    
    if not codes:
        logger.warning("未解析到任何股票代码")
        return

    logger.info(f"解析到 {len(codes)} 只股票，开始极速标注...")
    
    metadata = fetch_metadata_fast(codes)
    
    new_items = []
    for code in codes:
        meta = metadata.get(code, {})
        name = meta.get('name', '未知')
        sector = meta.get('sector', '未知')
        stype = meta.get('type', '未知')
        new_items.append(f"{code}|{name}|{sector}|{stype}")
    
    # 格式化输出，加上换行让 .env 更美观
    new_stock_list = "\n" + ",\n".join(new_items) + "\n"
    
    print("\n" + "="*50)
    print("生成的 STOCK_LIST 建议配置 (多行美化版):")
    print("="*50)
    print(f'STOCK_LIST="{new_stock_list}"')
    print("="*50 + "\n")
    
    confirm = input("是否直接更新 .env 文件? (y/n): ")
    if confirm.lower() == 'y':
        # 更新 env 文件，确保带引号以支持换行
        set_key(str(env_path), "STOCK_LIST", f'"{new_stock_list}"', quote_mode='never')
        logger.info(".env 文件已更新并自动格式化为多行！")
    else:
        logger.info("操作已取消。")

if __name__ == "__main__":
    main()
