import os
import requests
import json
import argparse
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
            
            # 基本信息和实时估值（天天基金 API）
            fund_info = self._get_fund_basic_info(fund_code)
            valuation = self._get_fund_valuation(fund_code)
            
            # 构建数据字典
            return {
                'code': fund_code,
                'name': fund_info.get('name', fund_code),
                'type': fund_info.get('type', '混合型'),
                'manager': fund_info.get('manager', '未知'),
                'latest_nav': fund_info.get('nav', '未知'),
                'valuation': valuation,
                'update_time': datetime.now().strftime('%Y-%m-%d')
            }
        except Exception as e:
            print(f"获取基金 {fund_code} 失败: {str(e)}")
            return {
                'code': fund_code,
                'name': fund_code,
                'type': '混合型',
                'manager': '获取失败',
                'latest_nav': '未知',
                'valuation': None,
                'update_time': datetime.now().strftime('%Y-%m-%d')
            }
    
    def _get_fund_basic_info(self, fund_code):
        """基金基本信息（备用方案）"""
        try:
            # 天天基金估值 API（实时）
            url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200 and len(response.text) > 10:
                # 解析 js 数据
                data_str = response.text.replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)
                return {
                    'name': data.get('name', fund_code),
                    'type': '股票型/混合型',
                    'manager': '未知',
                    'nav': data.get('dwjz', '未知')  # 单位净值
                }
        except Exception as e:
            print(f"获取基本信息失败: {str(e)}")
            
        return {'name': fund_code, 'type': '混合型', 'manager': '未知', 'nav': '未知'}
    
    def _get_fund_valuation(self, fund_code):
        """获取盘中估值（实时）"""
        try:
            url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200 and len(response.text) > 10:
                data_str = response.text.replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)
                return {
                    'valuation': data.get('gsz', ''),  # 估算净值
                    'valuation_date': data.get('gztime', ''),
                    'change_percent': data.get('gszzl', ''),  # 估算涨跌幅
                    'real_nav': data.get('dwjz', '')  # 实际净值
                }
        except Exception as e:
            print(f"获取估值失败: {str(e)}")
            
        return None
    
    def analyze_fund_with_ai(self, fund_data):
        """DeepSeek AI 分析基金（含推荐对比）"""
        
        # 构建估值信息
        valuation_str = ""
        if fund_data['valuation']:
            change = fund_data['valuation'].get('change_percent', '0')
            real_nav = fund_data['valuation'].get('real_nav', '未知')
            est_nav = fund_data['valuation'].get('valuation', '未知')
            valuation_str = f"最新净值: {real_nav} | 盘中估值: {est_nav} (涨跌: {change}%)"
        
        # 根据基金代码识别类型（简化判断）
        fund_type_hint = "混合偏股型，关注股票仓位和重仓行业"
        if '债' in fund_data.get('type', ''):
            fund_type_hint = "债券型，关注久期和信用债比例"
        elif '指数' in fund_data.get('type', ''):
            fund_type_hint = "指数型，关注跟踪误差和费率"

        prompt = f"""你是一位专业基金投顾（CFA持证人），请对以下基金进行深度分析，并给出同类型的优选对比（总字数<600字，严格格式）。

【基金信息】
名称代码：{fund_data['name']} ({fund_data['code']})
类型：{fund_data['type']}
基金经理：{fund_data['manager']}
{valuation_str}

【基金类型提示】
{fund_type_hint}

【输出格式 - 严格按照此格式，禁止Markdown符号，只能用emoji和中文】：

📊 基金诊断
• 名称代码：{fund_data['name']} ({fund_data['code']})
• 健康度评级：⭐⭐⭐⭐⭐（5星制，综合打分）
• 当前状态：🟢适合加仓 / 🟡持有观望 / 🔴考虑转换（必须明确）
• 适合人群：（如：稳健型/激进型/定投新手）

📈 业绩分析
• 近期表现：盘中涨跌幅如何？市场排名预估
• 风险特征：波动率、最大回撤预估评价
• 性价比：收益风险比评价

⚠️ 风险扫描
• 持仓风险：行业集中度、重仓股风险
• 规模风险：规模过大或过小的问题
• 经理风险：经理稳定性、投资风格

🔄 优化建议（给出具体对比和推荐）
基于该基金类型，对比市场同类：

如果这只表现一般：
• 同类型更优选择：（给出1-2只同类型明星基金代码和名称，格式：代码 名称，如"005827 易方达蓝筹精选"）
• 推荐理由：费率低/业绩稳/经理强等具体原因
• 替换策略：立即转换还是分批切换？

如果这只已很好：
• 互补配置：为了分散风险，可以搭配什么类型的基金？
• 具体代码：（给出具体基金代码，如"添加016482做平衡"）

💡 今日操作建议（明确具体）
• 定投：今日适合定投吗？（适合/不适合）
• 单笔：现在适合一次性买入吗？（适合/观望/暂停）
• 持仓：已有份额建议加仓/持有/部分赎回？
• 止损：如果亏损超过多少，建议转换？

【合规声明】以上对比仅基于公开数据分析，不构成投资建议，请根据自身风险承受能力决策。

【严禁】
• 禁止模糊表述（必须明确适合/不适合）
• 禁止预测具体涨跌点位
• 禁止保证收益承诺
• 禁止使用Markdown符号（井号、星号、减号、反引号等全部禁止）
• 只能用emoji、中文、数字、换行
"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.4,
            'max_tokens': 1200
        }
        
        try:
            print(f"正在调用DeepSeek分析 {fund_data['code']}...")
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=90
            )
            
            if response.status_code != 200:
                print(f"API错误: {response.status_code} - {response.text[:200]}")
                return f"❌ 分析失败，API状态码: {response.status_code}"
                
            result = response.json()
            
            if 'choices' not in result or not result['choices']:
                print(f"API返回异常: {result}")
                return "❌ AI返回格式异常"
            
            content = result['choices'][0]['message']['content']
            
            # 后处理保险：强制过滤Markdown符号
            content = (content
                      .replace('#', '')
                      .replace('**', '')
                      .replace('*', '•')
                      .replace('- ', '• ')
                      .replace('`', '')
                      .replace('>', '')
                      .replace('###', '')
                      .replace('##', '')
                      .replace('__', '')
                      .replace('【', '')
                      .replace('】', ''))
            
            return content
            
        except Exception as e:
            print(f"分析过程异常: {str(e)}")
            return f"❌ 分析异常: {str(e)}"
    
    def send_feishu(self, content):
        """推送到飞书"""
        if not self.feishu_url:
            print("错误：未配置飞书Webhook")
            return
            
        try:
            formatted = f"""
💰 每日基金诊断 | {datetime.now().strftime('%Y-%m-%d')}

{content}

---
📈 数据来源：天天基金 | 由 DeepSeek-R1 分析
⚠️ 风险提示：以上分析仅供参考，不构成投资建议。基金有风险，投资需谨慎。
            """
            
            payload = {
                "msg_type": "text",
                "content": {
                    "text": formatted
                }
            }
            
            response = requests.post(self.feishu_url, json=payload)
            print(f"飞书推送结果: {response.status_code}")
            
            if response.status_code != 200:
                print(f"飞书推送失败: {response.text}")
                
        except Exception as e:
            print(f"飞书推送异常: {str(e)}")
    
    def run(self, fund_codes_str):
        fund_codes = [c.strip() for c in fund_codes_str.split(',')]
        
        print(f"开始分析 {len(fund_codes)} 只基金: {fund_codes}")
        
        full_report = ""
        
        for i, code in enumerate(fund_codes, 1):
            print(f"\n正在分析第 {i}/{len(fund_codes)} 只基金: {code}")
            fund_data = self.fetch_fund_data(code)
            
            analysis = self.analyze_fund_with_ai(fund_data)
            full_report += f"━━━━━━━━━━━━\n【{i}】{analysis}\n\n"
        
        if not full_report.strip():
            full_report = "📭 今日基金分析失败，请检查网络或基金代码"
        
        self.send_feishu(full_report)
        print(f"\n完成！分析了 {len(fund_codes)} 只基金")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--funds', default='022477,016482,010011', help='基金代码，逗号分隔')
    parser.add_argument('--type', default='full', help='分析类型（保留参数兼容）')
    args = parser.parse_args()
    
    analyzer = FundAnalyzer()
    analyzer.run(args.funds)
