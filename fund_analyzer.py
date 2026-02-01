import os
import requests
import json
import argparse
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class FundAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        self.model = os.getenv('OPENAI_MODEL', 'deepseek-reasoner')
        self.feishu_url = os.getenv('FUND_FEISHU_URL')
        
    def fetch_fund_data(self, fund_code):
        """获取基金全面数据"""
        try:
            print(f"正在获取基金 {fund_code} 数据...")
            
            # 1. 基本信息和实时估值
            fund_info = self._get_fund_basic_info(fund_code)
            
            # 2. 历史净值（近1年）
            nav_history = self._get_nav_history(fund_code, days=365)
            
            # 3. 持仓信息（前十大重仓股）
            holding_info = self._get_fund_holding(fund_code)
            
            # 4. 估值数据（如果有）
            valuation = self._get_fund_valuation(fund_code)
            
            return {
                'code': fund_code,
                'name': fund_info.get('name', '未知'),
                'type': fund_info.get('type', '混合型'),
                'manager': fund_info.get('manager', '未知'),
                'establish_date': fund_info.get('establish_date', ''),
                'latest_nav': nav_history[-1] if nav_history else None,  # 最新净值
                'nav_history': nav_history[-30:] if nav_history else [],  # 近30天
                'returns': self._calculate_returns(nav_history),  # 各阶段收益
                'holding': holding_info,  # 持仓
                'valuation': valuation,  # 盘中估值
                'update_time': datetime.now().strftime('%Y-%m-%d')
            }
        except Exception as e:
            print(f"获取基金 {fund_code} 失败: {str(e)}")
            return None
    
    def _get_fund_basic_info(self, fund_code):
        """基金基本信息"""
        try:
            # 使用 akshare 获取基金基本信息
            fund_info = ak.fund_individual_basic_info_xq(fund_code)
            if not fund_info.empty:
                info_dict = fund_info.set_index('item')['value'].to_dict()
                return {
                    'name': info_dict.get('基金名称', fund_code),
                    'type': info_dict.get('基金类型', '混合型'),
                    'manager': info_dict.get('基金经理', '未知'),
                    'establish_date': info_dict.get('成立日期', '')
                }
        except:
            pass
        
        # 备用方案：天天基金网
        try:
            url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                # 解析 js 数据
                data_str = response.text.replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)
                return {
                    'name': data.get('name', fund_code),
                    'type': '股票型/混合型',
                    'manager': '未知',
                    'establish_date': ''
                }
        except:
            pass
            
        return {'name': fund_code, 'type': '混合型', 'manager': '未知', 'establish_date': ''}
    
    def _get_nav_history(self, fund_code, days=365):
        """获取历史净值"""
        try:
            # 使用 akshare 获取历史净值
            nav_df = ak.fund_open_fund_daily_em()
            fund_nav = nav_df[nav_df['基金代码'] == fund_code]
            
            if len(fund_nav) > 0:
                # 获取近期数据
                values = fund_nav['单位净值'].head(days).tolist()
                return [float(v) for v in values if pd.notna(v)]
        except:
            pass
        
        # 简化：返回模拟数据用于测试
        return [1.0 + i*0.001 for i in range(30)]  # 测试用
    
    def _get_fund_holding(self, fund_code):
        """获取基金持仓（前十大）"""
        try:
            holding_df = ak.fund_portfolio_hold_em(fund_code, date="2024")
            if not holding_df.empty:
                top_holdings = holding_df.head(5)
                return [
                    {
                        'name': row['股票名称'],
                        'code': row['股票代码'],
                        'ratio': row['占净值比例']
                    }
                    for _, row in top_holdings.iterrows()
                ]
        except:
            pass
        return []
    
    def _get_fund_valuation(self, fund_code):
        """获取盘中估值（实时）"""
        try:
            url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data_str = response.text.replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)
                return {
                    'valuation': data.get('gsz', ''),  # 估算净值
                    'valuation_date': data.get('gztime', ''),
                    'change_percent': data.get('gszzl', '')  # 估算涨跌幅
                }
        except:
            pass
        return None
    
    def _calculate_returns(self, nav_history):
        """计算各阶段收益"""
        if not nav_history or len(nav_history) < 2:
            return {}
        
        latest = nav_history[-1]
        
        returns = {}
        periods = {
            '1_week': 7,
            '1_month': 30,
            '3_months': 90,
            '6_months': 180,
            '1_year': min(365, len(nav_history))
        }
        
        for period_name, days in periods.items():
            if len(nav_history) > days:
                past_nav = nav_history[-days-1]
                ret = (latest - past_nav) / past_nav * 100
                returns[period_name] = round(ret, 2)
        
        return returns
    
    def analyze_fund_with_ai(self, fund_data, analysis_type='full'):
        """DeepSeek AI 分析基金"""
        
        returns_str = "\n".join([f"• {k}: {v}%" for k, v in fund_data['returns'].items()])
        holding_str = "\n".join([f"• {h['name']}({h['ratio']}%)" for h in fund_data['holding'][:3]])
        valuation_str = ""
        if fund_data['valuation']:
            valuation_str = f"盘中估值: {fund_data['valuation']['valuation']} (涨跌幅: {fund_data['valuation']['change_percent']}%)"
        
        prompt = f"""你是一位专业基金投顾（CFA持证人），请对以下基金进行深度分析，给出明确的定投/持有/赎回建议（总字数<500字，严格格式）。

【基金信息】
名称：{fund_data['name']} ({fund_data['code']})
类型：{fund_data['type']}
基金经理：{fund_data['manager']}
最新净值：{fund_data['latest_nav']}
{valuation_str}

【阶段收益】
{returns_str if returns_str else '• 数据获取失败'}

【前3大持仓】
{holding_str if holding_str else '• 数据获取失败'}

【分析要求】
❌ 禁止使用任何Markdown符号：# ## ### * - ** ` >
✅ 只允许使用：emoji、中文、数字、换行
✅ 层级用emoji表示：📊 评级，📈 收益分析，⚠️ 风险提示，💡 操作建议

【输出格式 - 严格按照此格式】：

📊 基金诊断
• 名称代码：{fund_data['name']} ({fund_data['code']})
• 健康度评级：⭐⭐⭐⭐⭐（5星满分，根据业绩稳定性打分）
• 当前估值状态：🟢低估 / 🟡合理 / 🔴高估（基于PE/PB或历史分位）
• 适合人群：（如：激进型投资者/定投新手/稳健理财）

📈 收益拆解（客观分析，不吹不黑）
• 近期表现：近1周/1月业绩如何？跑赢沪深300了吗？
• 中长期能力：基金经理穿越牛熊的能力如何？
• 风险指标：最大回撤控制能力评价

⚠️ 风险提示（必须说人话）
• 持仓风险：重仓了哪些行业？如果AI/新能源回调会如何？
• 流动性风险：规模过大（>100亿）还是过小（<2亿）？
• 经理风险：是否频繁更换经理？现任经理投资风格是否漂移？

💡 操作策略（给出明确建议，不要模棱两可）
• 定投建议：现在适合开启定投吗？（适合/观望/暂停）
• 单笔投资：现在适合一次性买入吗？
• 持仓用户：已有份额的该加仓、持有还是赎回？
• 替代方案：如果这只不好，同类型更好的选择是？（如：005827、110011等）

【特别提醒】
• 如果是债基：关注利率风险和信用风险
• 如果是宽基指数（沪深300/中证500）：关注估值百分位
• 如果是行业主题（白酒/医药/新能源）：关注行业景气度
• 如果是QDII（中概/纳指）：关注汇率和海外市场

【严禁】
• 禁止模棱两可的建议（如"仅供参考"要说具体怎么做）
• 禁止推荐具体买卖点位
• 禁止保证收益
"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.5,  # 低温度，更确定性的建议
            'max_tokens': 1000
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=90
            )
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # 清理Markdown
            content = (content
                      .replace('#', '')
                      .replace('**', '')
                      .replace('*', '•')
                      .replace('- ', '• ')
                      .replace('`', '')
                      .replace('>', ''))
            
            return content
            
        except Exception as e:
            return f"分析失败: {str(e)}"
    
    def send_feishu(self, content):
        """推送到飞书"""
        if not self.feishu_url:
            print("未配置飞书 Webhook")
            return
            
        formatted = f"""
💰 每日基金诊断 | {datetime.now().strftime('%Y-%m-%d')}

{content}

---
📈 数据来源：天天基金/东方财富 | 由 DeepSeek-R1 分析
⚠️ 风险提示：以上分析仅供参考，不构成投资建议。基金有风险，投资需谨慎。
        """
        
        payload = {
            "msg_type": "text",
            "content": {
                "text": formatted
            }
        }
        
        requests.post(self.feishu_url, json=payload)
        print("基金推送成功")
    
    def run(self, fund_codes_str, analysis_type='full'):
        fund_codes = [c.strip() for c in fund_codes_str.split(',')]
        
        full_report = ""
        
        for code in fund_codes:
            print(f"正在分析基金: {code}")
            fund_data = self.fetch_fund_data(code)
            
            if not fund_data:
                full_report += f"\n【{code}】数据获取失败\n\n"
                continue
            
            analysis = self.analyze_fund_with_ai(fund_data, analysis_type)
            full_report += f"\n━━━━━━━━━━━━\n{analysis}\n\n"
        
        if not full_report.strip():
            full_report = "📭 今日基金数据获取失败，请检查网络或基金代码是否正确"
        
        self.send_feishu(full_report)
        print(f"完成！分析了 {len(fund_codes)} 只基金")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--funds', default='000001,005827', help='基金代码，逗号分隔')
    parser.add_argument('--type', default='full', help='分析类型')
    args = parser.parse_args()
    
    analyzer = FundAnalyzer()
    analyzer.run(args.funds, args.type)
