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
        
        self.topics = [
            "sleep_circadian_rhythm",
            "nutrition_metabolism", 
            "exercise_physiology",
            "cognitive_psychology",
            "microbiome_gut_health",
            "light_vision_health",
        ]
    
    def fetch_wikipedia_fact(self):
        """从Wikipedia获取今日精选"""
        try:
            wiki = wikipediaapi.Wikipedia('DailyScienceBot/1.0', 'en')
            
            topics = [
                "Circadian rhythm", "Melatonin", "Vitamin D", 
                "Hypertension", "Caffeine", "Blue light",
                "Gut microbiota", "REM sleep", "Insulin resistance",
                "Hydration", "Fiber", "Protein intake"
            ]
            
            topic = random.choice(topics)
            print(f"正在查询Wiki: {topic}")
            
            page = wiki.page(topic)
            
            if not page.exists():
                print(f"Wiki页面不存在: {topic}")
                return None
                
            return {
                'title': topic,
                'summary': page.summary[:800],
                'url': page.fullurl,
                'source': 'Wikipedia (CC BY-SA)'
            }
        except Exception as e:
            print(f"Wiki获取失败: {str(e)}")
            return None
    
    def fetch_pubmed_health_tip(self):
        """从PubMed获取今日健康循证研究"""
        try:
            query = "(sleep[Title] OR diet[Title] OR exercise[Title]) AND (meta-analysis[Title] OR randomized[Title])"
            
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                'db': 'pubmed',
                'term': query,
                'retmax': 5,
                'sort': 'date',
                'retmode': 'json',
                'datetype': 'pdat',
                'reldate': 7
            }
            
            print("正在查询PubMed...")
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            idlist = data['esearchresult']['idlist']
            
            if not idlist:
                print("PubMed未找到新文献")
                return None
                
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
        except Exception as e:
            print(f"PubMed获取失败: {str(e)}")
            return None
    
    def verify_and_summarize(self, wiki_data, pubmed_data):
        """用DeepSeek整合并强调证据等级"""
        try:
            wiki_title = wiki_data['title'] if wiki_data else '健康新知'
            wiki_summary = wiki_data['summary'] if wiki_data else '暂无百科条目'
            pubmed_title = pubmed_data['title'] if pubmed_data else '今日无新研究'
            pubmed_journal = pubmed_data['journal'] if pubmed_data else 'N/A'
            
            content = f"""
今日科普主题：{wiki_title}

背景知识（来自百科）：
{wiki_summary}

最新研究（来自PubMed）：
{pubmed_title}
来源期刊：{pubmed_journal}
"""
            
            prompt = f"""你是一位循证医学科普作家，请将以下信息改写为【有明确来源标签】的生活建议（总字数<400字）。

【重要格式要求 - 严格遵守】：
❌ 禁止使用任何Markdown符号
✅ 只允许使用：emoji、中文、英文、数字、换行、空格
✅ 层级用emoji表示：🧠 冷知识，📖 解释，🔬 来源，❌ 辟谣
✅ 列表用 • 符号（中文输入法里的点）

【内容】
{content}

【输出格式】：

🧠 今日冷知识
（用1句话讲一个反直觉的科学事实）

📖 为什么？
（解释机制，100字内，用大白话）

🔬 证据来源
• ✅ 强证据（来自：{pubmed_journal}）：一句话结论
• 📚 参考知识（来自：Wikipedia）：背景补充
• ⚠️ 注意事项：什么人群不适用？

❌ 常见谣言澄清
（针对这个主题，市面上流传的错误说法，用❌标记）

【严禁】：
• 禁止出现"中医认为"、"专家表示"等模糊来源
• 禁止推荐保健品/具体品牌
• 禁止绝对化表述，改用"研究显示"
• 禁止任何Markdown符号
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
            
            print("正在调用DeepSeek分析...")
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"DeepSeek API错误: {response.status_code} - {response.text}")
                return f"⚠️ AI分析失败，状态码: {response.status_code}"
                
            result = response.json()
            
            if 'choices' not in result or not result['choices']:
                print(f"DeepSeek返回异常: {result}")
                return "⚠️ AI返回格式异常"
            
            content_result = result['choices'][0]['message']['content']
            
            # 后处理保险
            content_result = (content_result
                             .replace('#', '')
                             .replace('**', '')
                             .replace('*', '•')
                             .replace('- ', '• ')
                             .replace('`', '')
                             .replace('>', '')
                             .replace('###', '')
                             .replace('##', ''))
            
            return content_result
            
        except Exception as e:
            print(f"生成过程异常: {str(e)}")
            return f"⚠️ 内容生成失败: {str(e)}"
    
    def run(self):
        print("开始获取生活科普数据...")
        wiki_fact = self.fetch_wikipedia_fact()
        pubmed_study = self.fetch_pubmed_health_tip()
        
        print(f"Wiki获取结果: {'成功' if wiki_fact else '失败'}")
        print(f"PubMed获取结果: {'成功' if pubmed_study else '失败'}")
        
        if not wiki_fact and not pubmed_study:
            self.send_feishu("📭 今日科普素材获取失败\n可能原因：\n• Wikipedia API被墙\n• PubMed无新文献\n• 网络超时")
            return
        
        print("开始生成内容...")
        content = self.verify_and_summarize(wiki_fact, pubmed_study)
        
        if not content or len(content.strip()) < 50:
            print(f"内容生成异常，长度: {len(content) if content else 0}")
            content = "⚠️ 内容生成失败，请检查DeepSeek API状态"
        
        footer = f"""
链接核查：
• 百科来源：{wiki_fact['source'] if wiki_fact else 'N/A'} {wiki_fact['url'] if wiki_fact else '无'}
• 研究来源：{pubmed_study['source'] if pubmed_study else 'N/A'} {pubmed_study['url'] if pubmed_study else '无'}
⚖️ 免责声明：以上信息仅供科普，不作为医疗建议，具体诊疗请咨询医师。
"""
        
        full_message = content + footer
        self.send_feishu(full_message)
        print("生活科普推送成功")
    
    def send_feishu(self, text):
        if not self.feishu_url:
            print("错误：未配置飞书Webhook")
            return
            
        try:
            payload = {
                "msg_type": "text",
                "content": {"text": f"🌟 循证生活 | {datetime.now().strftime('%m-%d')}\n\n{text}"}
            }
            
            response = requests.post(self.feishu_url, json=payload)
            print(f"飞书推送结果: {response.status_code}")
            
            if response.status_code != 200:
                print(f"飞书推送失败: {response.text}")
                
        except Exception as e:
            print(f"飞书推送异常: {str(e)}")

if __name__ == '__main__':
    bot = LifeScienceBot()
    bot.run()
