import os
import json
import requests
import arxiv
from datetime import datetime, timedelta, timezone
import argparse

class PaperAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        self.model = os.getenv('OPENAI_MODEL', 'deepseek-reasoner')
        # 论文可以用单独推送渠道，如果没有就用股票同一个
        self.feishu_url = os.getenv('PAPER_FEISHU_URL') or os.getenv('FEISHU_WEBHOOK_URL')
        
    def fetch_recent_papers(self, keywords, max_results=3):
        """抓取最近24小时的论文"""
        client = arxiv.Client()
        papers = []
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        for keyword in keywords:
            search = arxiv.Search(
                query=keyword,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )
            
            for result in client.results(search):
                # 只取最近24小时的
                if result.published >= yesterday:
                    papers.append({
                        'title': result.title,
                        'authors': [str(a) for a in result.authors[:3]],
                        'summary': result.summary,
                        'pdf_url': result.pdf_url,
                        'published': result.published.strftime('%Y-%m-%d'),
                        'categories': result.categories,
                        'keyword': keyword
                    })
        return papers

    def analyze_with_ai(self, paper):
        """用 DeepSeek 分析论文"""
        prompt = f"""
你是一位专业学术助手，请快速解读这篇论文，输出格式严格如下：

📌 **标题**：{paper['title']}
👤 **作者**：{', '.join(paper['authors'])}
🏷️ **领域**：{paper['categories'][0] if paper['categories'] else '未分类'}

🔍 **一句话总结**：（用中文一句话概括核心创新，不超过50字）

💡 **关键亮点**：
- 方法：（关键技术/方法）
- 结果：（主要性能提升或发现）
- 意义：（对学术界/工业界的价值）

⚠️ **适合人群**：（如：推荐NLP研究者关注/适合推荐系统方向/可跳过等）

原始摘要：{paper['summary'][:1000]}
        """
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=120
            )
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            return f"分析失败: {str(e)}"

    def send_feishu(self, content):
        """推送到飞书"""
        if not self.feishu_url:
            print("未配置飞书 Webhook")
            return
            
        formatted = f"""
🎓 **每日论文速递** | {datetime.now().strftime('%Y-%m-%d')}

{content}

---
📚 来源：arXiv | 由 DeepSeek-R1 分析
        """
        
        payload = {
            "msg_type": "text",
            "content": {
                "text": formatted
            }
        }
        
        requests.post(self.feishu_url, json=payload)
        print("论文推送成功")

    def run(self, keywords_str, max_results):
        keywords = [k.strip() for k in keywords_str.split(',')]
        papers = self.fetch_recent_papers(keywords, max_results)
        
        if not papers:
            self.send_feishu("📭 今日暂无新论文（或arXiv未更新）")
            return
            
        # 去重
        seen_titles = set()
        unique_papers = []
        for p in papers:
            if p['title'] not in seen_titles:
                seen_titles.add(p['title'])
                unique_papers.append(p)
        
        full_report = f"📊 共发现 {len(unique_papers)} 篇新论文\n\n"
        
        for i, paper in enumerate(unique_papers, 1):
            print(f"正在分析第 {i} 篇: {paper['title'][:50]}...")
            analysis = self.analyze_with_ai(paper)
            full_report += f"━━━━━━━━━━━━\n【{i}】{analysis}\n\n"
        
        self.send_feishu(full_report)
        print(f"完成！分析了 {len(unique_papers)} 篇论文")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--keywords', default='LLM,RAG,Agent', help='搜索关键词')
    parser.add_argument('--max', type=int, default=3, help='每关键词数量')
    args = parser.parse_args()
    
    analyzer = PaperAnalyzer()
    analyzer.run(args.keywords, args.max)
