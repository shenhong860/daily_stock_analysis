import os
import requests
import feedparser
from datetime import datetime

class CNSAnalyzer:
    """只监控CNS主刊及大子刊"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        self.model = os.getenv('OPENAI_MODEL', 'deepseek-reasoner')
        self.feishu_url = os.getenv('CNS_FEISHU_URL')
        
        # CNS及大子刊RSS（严格筛选）
        self.journals = {
            'Nature': 'https://www.nature.com/nature.rss',
            'Nature Medicine': 'https://www.nature.com/nm.rss',
            'Nature Cancer': 'https://www.nature.com/natcancer.rss',
            'Cell': 'https://www.cell.com/cell/current.rss',
            'Cancer Cell': 'https://www.cell.com/cancer-cell/current.rss',
            'Cell Stem Cell': 'https://www.cell.com/cell-stem-cell/current.rss',
            'Immunity': 'https://www.cell.com/immunity/current.rss',
            'Science': 'https://www.science.org/rss/news_current.xml',
            'Science Translational Medicine': 'https://www.science.org/rss/tm_current.xml',
            'Molecular Cell': 'https://www.cell.com/molecular-cell/current.rss',
            'Nature Cell Biology': 'https://www.nature.com/ncb.rss',
            'Nature Immunology': 'https://www.nature.com/ni.rss',
            'Cell Metabolism': 'https://www.cell.com/cell-metabolism/current.rss',
            'Neuron': 'https://www.cell.com/neuron/current.rss'
        }
        
        # 关键词过滤（只保留医学/分子生物学相关）
        self.keywords = [
            'cancer', 'tumor', 'immunotherapy', 'single-cell', 'spatial',
            'CRISPR', 'genome', 'transcriptome', 'proteomics', 'metabolism',
            'stem cell', 'differentiation', 'microenvironment', 'signaling',
            'pathway', 'mechanism', 'therapeutic', 'clinical trial'
        ]
    
    def fetch_cns_papers(self):
        """抓取各顶刊最新文章"""
        papers = []
        
        for journal_name, rss_url in self.journals.items():
            try:
                feed = feedparser.parse(rss_url)
                # 只取最近24小时的前2篇
                for entry in feed.entries[:2]:
                    # 检查是否为生物医学相关
                    content = f"{entry.title} {entry.get('summary', '')}".lower()
                    
                    if any(k in content for k in self.keywords):
                        papers.append({
                            'title': entry.title,
                            'journal': journal_name,
                            'link': entry.link,
                            'summary': entry.get('summary', '')[:500],
                            'published': entry.get('published', 'Today')
                        })
                        
                        if len(papers) >= 5:  # 每天最多5篇，保证质量
                            return papers
            except:
                continue
        
        return papers
    
    def deep_analysis(self, paper):
        """如同导师审稿般的深度分析"""
        prompt = f"""你是Cell/Nature期刊的资深审稿人，请对这篇顶刊文章进行"研究生组会汇报"级别的深度解析（总字数<600字，严格结构）：

【文章信息】
期刊：{paper['journal']}
标题：{paper['title']}
摘要片段：{paper['summary']}

【要求输出 - 不符合顶刊水平直接指出】：

🏆 **研究档次**
• 期刊实力：{paper['journal']} (IF: {self._get_if(paper['journal'])})
• 研究类型：是【概念突破】/【技术革命】/【临床转化】/【机制深挖】？
• 一句话评级：这可能是领域里程碑/重要补充/ incremental work?

🧬 **核心发现（精华！）**
• 颠覆了哪个传统认知？或填补了哪个空白？
• 关键实验设计：用什么新技术/模型解决了什么老问题？
• 数据规模：涉及多少样本/细胞/基因？（体现工作量）

💊 **医学意义（如果你是临床医生）**
• 能立刻改变诊疗指南吗？还是需要10年转化？
• 潜在靶点是否已有药物可用？（老药新用 vs 全新靶点）

⚠️ **审稿人视角的质疑（Critical Thinking）**
• 实验设计是否有漏洞？（如：仅用细胞系，缺乏体内验证）
• 机制是否过于相关论，缺乏因果？（如：仅用敲低，无 rescue）
• 样本是否有偏倚？（如：仅早期患者，或特定人种）

🎯 **你能学到什么？**
• 技术：可迁移到你课题的方法（如：某新型测序方案）
• 思路：如何提出一个值得发CNS的科学问题？
• 写作：标题/摘要的哪些技巧值得模仿？

【严禁套路化评价，必须有具体批判点】
"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.4,  # 降低温度，更批判性
            'max_tokens': 1200
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=90
            )
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"分析失败: {str(e)}"
    
    def _get_if(self, journal):
        """简化IF映射"""
        ifs = {
            'Nature': '64.8', 'Science': '56.9', 'Cell': '64.5',
            'Nature Medicine': '82.9', 'Cancer Cell': '48.8',
            'Cell Stem Cell': '23.9', 'Immunity': '32.4',
            'Nature Cancer': '23.5', 'Science Translational Medicine': '17.1',
            'Molecular Cell': '17.0', 'Neuron': '16.2',
            'Nature Cell Biology': '17.3', 'Nature Immunology': '27.7',
            'Cell Metabolism': '31.3'
        }
        return ifs.get(journal, '20+')
    
    def run(self):
        papers = self.fetch_cns_papers()
        
        if not papers:
            self.send_feishu("📭 今日CNS无生物医学相关新文，或抓取被墙")
            return
        
        report = f"📊 扫描 {len(self.journals)} 本顶刊，精选 {len(papers)} 篇\n\n"
        
        for i, paper in enumerate(papers, 1):
            analysis = self.deep_analysis(paper)
            report += f"━━━━━━━━━━━━\n【{i}】{paper['journal']} | {paper['title'][:60]}...\n{analysis}\n🔗 {paper['link']}\n\n"
        
        self.send_feishu(report)
        print(f"CNS推送完成，共{len(papers)}篇")
    
    def send_feishu(self, text):
        if not self.feishu_url:
            print("未配置飞书")
            return
            
        payload = {
            "msg_type": "text",
            "content": {"text": f"🏆 **CNS晨读** | {datetime.now().strftime('%m-%d')}\n\n{text}"}
        }
        requests.post(self.feishu_url, json=payload)

if __name__ == '__main__':
    analyzer = CNSAnalyzer()
    analyzer.run()
