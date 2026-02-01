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
        """精简版论文分析，适合快速阅读"""
        # 检测是否为单细胞/生物信息学领域
        categories = [c.lower() for c in paper['categories']]
        is_bio = any(x in str(categories) for x in ['bio', 'genomics', 'rna', 'cell', 'medical'])
        
        # 根据领域调整关键词
        method_hint = "单细胞(scRNA-seq)注意dropout/批次效应/降维质量控制" if is_bio else "关注深度学习架构/损失函数设计/计算效率"
        
        prompt = f"""你是一位高效的学术猎手，请用极简方式分析这篇论文，每部分严格限制字数：

【论文】{paper['title']}
【作者】{', '.join(paper['authors'][:2])}等
【领域】{paper['categories'][0]}

摘要：{paper['summary'][:800]}...

请按以下格式输出（总字数<600字）：

🔍 **摘要翻译**（100字内）：
准确翻译核心贡献

💡 **为什么做？**（痛点，50字内）：
现有方法缺陷+本文解决思路

⚙️ **怎么做？**（ Pipeline，150字内）：
1.输入→2.核心步骤→3.输出，避免术语堆砌，用"动词+对象"格式

📊 **好在哪里？**（50字内）：
关键指标提升（如ARI+15%/速度x3倍）vs SOTA方法

⚠️ **坑在哪？**（30字内）：
计算开销/数据依赖/参数敏感性问题

🛠️ **复现难度**（30字内）：
开源？（GitHub:有/无）| 硬件要求 | 关键依赖包

🎯 **速记版**（20字内核心+3步Pipeline）：
核心：____（如"图卷积去批次"）
3步：1.____ 2.____ 3.____（用初中词汇描述，勿用论文生造词）

领域提示：{method_hint}
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
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=90
            )
            result = response.json()
            analysis = result['choices'][0]['message']['content']
            
            return f"{analysis}\n\n📄 {paper['pdf_url']}"
            
        except Exception as e:
            return f"❌ 分析失败: {str(e)}"
        

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
