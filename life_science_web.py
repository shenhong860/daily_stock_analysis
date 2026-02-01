import os
import requests
import json
import random
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup

class LifeScienceWeb:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        self.model = os.getenv('OPENAI_MODEL', 'deepseek-reasoner')
        self.feishu_url = os.getenv('LIFE_FEISHU_URL')
        
    def fetch_zhihu_health(self):
        """抓取知乎健康话题热榜"""
        try:
            # 知乎热榜API（公开）
            url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            
            # 筛选健康相关话题
            health_keywords = ['健康', '医学', '医生', '疾病', '减肥', '睡眠', '营养', '运动', '疫苗', '体检']
            health_items = []
            
            for item in data.get('data', []):
                title = item.get('target', {}).get('title', '')
                if any(k in title for k in health_keywords):
                    health_items.append({
                        'title': title,
                        'url': item.get('target', {}).get('url', ''),
                        'source': '知乎热榜'
                    })
            
            if health_items:
                return random.choice(health_items[:5])  # 前5个随机选1个
        except Exception as e:
            print(f"知乎抓取失败: {str(e)}")
        return None
    
    def fetch_who_daily(self):
        """抓取WHO每日健康提示"""
        try:
            # WHO新闻RSS
            url = "https://www.who.int/rss-feeds/news-english.xml"
            feed = feedparser.parse(url)
            
            if feed.entries:
                entry = feed.entries[0]  # 最新一条
                return {
                    'title': entry.title,
                    'summary': entry.summary[:500] if hasattr(entry, 'summary') else '',
                    'url': entry.link,
                    'source': 'WHO'
                }
        except Exception as e:
            print(f"WHO抓取失败: {str(e)}")
        return None
    
    def fetch_pubmed_today(self):
        """抓取今日PubMed健康科普（简化版）"""
        try:
            # 搜索近7天的高关注度健康主题
            query = "(health[Title] OR diet[Title] OR sleep[Title]) AND (review[Publication Type])"
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                'db': 'pubmed',
                'term': query,
                'retmax': 3,
                'sort': 'date',
                'retmode': 'json',
                'reldate': 7  # 近7天
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            idlist = data['esearchresult']['idlist']
            
            if idlist:
                # 取第一篇详情
                fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                fetch_params = {
                    'db': 'pubmed',
                    'id': idlist[0],
                    'retmode': 'json'
                }
                fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=10)
                article = fetch_resp.json()['result'][idlist[0]]
                
                return {
                    'title': article.get('title', ''),
                    'source': f"PubMed - {article.get('source', '')}",
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{idlist[0]}/"
                }
        except Exception as e:
            print(f"PubMed抓取失败: {str(e)}")
        return None
    
    def generate_content(self, topic):
        """用AI生成科普解读"""
        if not topic:
            return self.fallback_content()
        
        prompt = f"""你是一位医学科普博主，请基于以下今日热点话题，写一篇【朋友圈风格的科普短文】（总字数<400字，禁止Markdown符号，只能用emoji和中文）。

【今日话题】
来源：{topic.get('source', '网络')}
标题：{topic.get('title', '')}
{topic.get('summary', '')}

【要求】：
🧠 现象解读：为什么大家关注这个话题？（用1句话点出痛点）
📖 科学原理：用大白话解释机制（100字内）
✅ 正确做法：给3条具体可操作的建议（如：1.每天7小时睡眠 2.睡前1小时不看手机 3.卧室温度20度）
❌ 常见误区：辟谣1个相关错误认知

【风格】：
• 像朋友分享经验，不要说教
• 每段用emoji开头
• 禁止用# * - > 【】等符号
• 中文表达，专业术语要解释
"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 800
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=60
            )
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # 清理格式
            content = (content
                      .replace('#', '')
                      .replace('**', '')
                      .replace('*', '')
                      .replace('- ', '')
                      .replace('`', '')
                      .replace('>', '')
                      .replace('【', '')
                      .replace('】', ''))
            
            return content
            
        except Exception as e:
            print(f"AI生成失败: {str(e)}")
            return self.fallback_content(topic)
    
    def fallback_content(self, topic=None):
        """备用内容（AI或网络失败时用）"""
        if topic:
            return f"""🧠 今日话题：{topic['title']}

📖 科学解读：这个话题涉及健康科学与日常生活的交叉，建议查阅权威医学期刊获取详细信息。

✅ 建议做法：
• 关注权威医学机构发布的指南
• 咨询专业医师获取个性化建议
• 保持批判性思维，辨别网络信息

❌ 注意辟谣：网络信息需谨慎甄别，请以《中国居民膳食指南》等官方文件为准

📚 来源：{topic.get('source', '网络')} | {topic.get('url', '')}"""
        else:
            return """🧠 今日科普：健康生活方式的重要性

📖 科学原理：WHO研究表明，生活方式占健康影响因素60%以上。

✅ 今日建议：
• 保持7-8小时优质睡眠
• 每天30分钟中等强度运动
• 多吃蔬菜水果，限制添加糖

❌ 误区提醒：不要盲目相信偏方，循证医学才是金标准"""
    
    def run(self):
        print("开始抓取联网数据...")
        
        # 多源抓取，优先级：知乎 > WHO > PubMed
        topic = None
        sources_checked = []
        
        topic = self.fetch_zhihu_health()
        sources_checked.append("知乎")
        if topic:
            print(f"从知乎获取话题: {topic['title'][:30]}...")
        else:
            print("知乎无数据，尝试WHO...")
            topic = self.fetch_who_daily()
            sources_checked.append("WHO")
            
        if not topic:
            print("WHO无数据，尝试PubMed...")
            topic = self.fetch_pubmed_today()
            sources_checked.append("PubMed")
        
        if not topic:
            print("所有网络源失败，使用本地备用...")
            topic = {
                'title': '今日健康建议',
                'source': '本地知识库',
                'url': ''
            }
        
        print(f"使用数据源: {topic.get('source', '未知')}")
        
        # 生成内容
        content = self.generate_content(topic)
        
        # 组装页脚
        footer = f"""
💡 话题来源：{topic.get('source', '综合')} 
🔗 原文链接：{topic.get('url', '详见相关报道')}
📡 数据抓取：{'/'.join(sources_checked)} | 生成时间：{datetime.now().strftime('%H:%M')}
⚖️ 免责声明：仅供参考，具体诊疗请咨询医师
"""
        
        full_message = content + footer
        self.send_feishu(full_message)
        print("推送完成")
    
    def send_feishu(self, text):
        if not self.feishu_url:
            print("未配置飞书")
            return
            
        try:
            payload = {
                "msg_type": "text",
                "content": {"text": f"🌐 每日健康速递 | {datetime.now().strftime('%m-%d')}\n\n{text}"}
            }
            response = requests.post(self.feishu_url, json=payload)
            print(f"推送状态: {response.status_code}")
        except Exception as e:
            print(f"推送失败: {str(e)}")

if __name__ == '__main__':
    bot = LifeScienceWeb()
    bot.run()
