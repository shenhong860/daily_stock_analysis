import os
import requests
import random
from datetime import datetime
import wikipediaapi

class LifeScienceBot:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        self.model = os.getenv('OPENAI_MODEL', 'deepseek-reasoner')
        self.feishu_url = os.getenv('LIFE_FEISHU_URL')
        
        # 权威事实来源库（每日随机选一个主题深挖）
        self.topics = [
            "sleep_circadian_rhythm",  # 睡眠与昼夜节律
            "nutrition_metabolism",    # 营养代谢（有临床证据的）
            "exercise_physiology",     # 运动生理
            "cognitive_psychology",    # 认知心理
            "microbiome_gut_health",   # 肠道菌群（有Cell/Nature实证的）
            "light_vision_health",     # 光线与视力健康
        ]
    
    def fetch_wikipedia_fact(self):
        """从Wikipedia获取今日精选（经过同行评议的科普）"""
        wiki = wikipediaapi.Wikipedia('DailyScienceBot/1.0', 'en')
        
        # 获取"On this day"历史上的科学发现，或随机高质量词条
        topics = [
            "Circadian rhythm", "Melatonin", "Vitamin D", 
            "Hypertension", "Caffeine", "Blue light",
            "Gut microbiota", "REM sleep", "Insulin resistance"
        ]
        
        topic = random.choice(topics)
        page = wiki.page(topic)
        
        if not page.exists():
            return None
            
        return {
            'title': topic,
            'summary': page.summary[:800],
            'url': page.fullurl,
            'source': 'Wikipedia (CC BY-SA)'
        }
    
    def fetch_pubmed_health_tip(self):
        """从PubMed获取今日健康循证研究（近7天高分综述）"""
        # 搜索高质量健康建议（Meta分析或RCT）
        query = "(sleep[Title] OR diet[Title] OR exercise[Title]) AND (meta-analysis[Title] OR randomized[Title])"
        
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': 5,
            'sort': 'date',
            'retmode': 'json',
            'datetype': 'pdat',  # 发表日期
            'reldate': 7  # 最近7天
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            idlist = data['esearchresult']['idlist']
            
            if not idlist:
                return None
                
            # 获取第一篇详情
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
                'journal': article.get('source', ''),
                'author': article.get('sortfirstauthor', ''),
                'pmid': idlist[0],
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{idlist[0]}/",
                'source': f"PubMed - {article.get('source', '')}"
            }
        except:
            return None
    
    def verify_and_summarize(self, wiki_data, pubmed_data):
        """用DeepSeek整合并强调证据等级"""
        
        content = f"""
今日科普主题：{wiki_data['title'] if wiki_data else '健康新知'}

背景知识（来自百科）：
{wiki_data['summary'] if wiki_data else '暂无百科条目'}

最新研究（来自PubMed）：
{pubmed_data['title'] if pubmed_data else '今日无新研究'}
来源期刊：{pubmed_data['journal'] if pubmed_data else 'N/A'}
"""
        
        prompt = f"""你是一位循证医学科普作家，请将以下信息改写为【有明确来源标签】的生活建议（总字数<400字）。必须遵循规则：

【内容】
{content}

【输出格式 - 严格遵守】：

🧠 **今日冷知识**
（用1句话讲一个反直觉的科学事实，带⚠️警示或✅建议）

📖 **为什么？**
（解释机制，100字内，用大白话）

🔬 **证据来源**（必须明确标注）：
- ✅ **强证据**（来自：{pubmed_data['journal'] if pubmed_data else 'Cochrane系统评价/Meta分析'}）：一句话结论
- 📚 **参考知识**（来自：Wikipedia/WHO指南）：背景补充
- ⚠️ **注意事项**：什么人群不适用？（如：孕妇/慢性病患者需咨询医生）

❌ **常见谣言澄清**（重要！）：
针对这个主题，市面上流传的错误说法（如"睡前喝牛奶助眠"等伪科学），用❌标记并简要辟谣。

【严禁】：
- 禁止出现"中医认为"、"专家表示"等模糊来源
- 禁止推荐保健品/具体品牌
- 禁止绝对化表述（"一定"、"肯定"），改用"研究显示"、"证据表明"
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
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"生成失败: {str(e)}"
    
    def run(self):
        # 获取数据
        wiki_fact = self.fetch_wikipedia_fact()
        pubmed_study = self.fetch_pubmed_health_tip()
        
        if not wiki_fact and not pubmed_study:
            self.send_feishu("📭 今日科普素材获取失败，请手动检查网络")
            return
        
        # 生成内容
        content = self.verify_and_summarize(wiki_fact, pubmed_study)
        
        # 添加页脚来源
        footer = f"""
---
📚 **今日来源核查**：
• 百科来源：{wiki_fact['source'] if wiki_fact else 'N/A'} | 🔗 {wiki_fact['url'] if wiki_fact else ''}
• 研究来源：{pubmed_study['source'] if pubmed_study else 'N/A'} | 🔗 {pubmed_study['url'] if pubmed_study else ''}
⚖️ **免责声明**：以上信息仅供科普，不作为医疗建议，具体诊疗请咨询医师。
        """
        
        self.send_feishu(content + footer)
        print("生活科普推送成功")
    
    def send_feishu(self, text):
        if not self.feishu_url:
            print("未配置飞书")
            return
            
        payload = {
            "msg_type": "text",
            "content": {"text": f"🌟 **循证生活** | {datetime.now().strftime('%m-%d')}\n\n{text}"}
        }
        requests.post(self.feishu_url, json=payload)

if __name__ == '__main__':
    bot = LifeScienceBot()
    bot.run()
