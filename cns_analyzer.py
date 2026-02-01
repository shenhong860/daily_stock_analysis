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
                # 只取最近的前2篇
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
        """修复版：禁止Markdown，使用纯文本Emoji格式"""
        prompt = f"""你是Cell/Nature期刊的资深审稿人，请对这篇顶刊文章进行"研究生组会汇报"级别的深度解析。

【重要格式要求 - 严格遵守】：
❌ 禁止使用任何Markdown符号：# ## ### * - ** ` > 等
✅ 只允许使用：emoji、中文、英文、数字、换行、空格
✅ 层级用emoji表示：🏆 主标题，🧬 子标题，• 列表项（用中文顿号或点号，不要用*）
✅ 链接单独一行放最后

【文章信息】
期刊：{paper['journal']}
标题：{paper['title']}
摘要片段：{paper['summary']}

【输出格式模板 - 严格按照此格式】：

🏆 研究档次
期刊：{paper['journal']} (IF: {self._get_if(paper['journal'])})
类型：【概念突破】或【技术革命】或【临床转化】或【机制深挖】
评级：一句话（如：里程碑工作/重要补充/incremental work）

🧬 核心发现（精华）
• 颠覆认知：一句话概括（如：颠覆了什么传统认知？）
• 关键技术：用什么新技术解决了什么老问题？
• 数据规模：涉及多少样本/细胞/基因？

💊 医学意义
• 临床价值：能否立刻改变诊疗指南？还是需要10年转化？
• 靶点现状：是否已有药物可用？

⚠️ 审稿人质疑
• 设计漏洞：（如：仅用细胞系缺乏体内验证）
• 机制深度：相关还是因果？
• 样本偏倚：（如：仅早期患者）

🎯 你能学到
• 技术：可迁移的方法
• 思路：如何提出CNS级科学问题？

链接：{paper['link']}

【字数限制】总字数<500字，每部分简短精炼，不要展开长篇大论。
"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.4,
            'max_tokens': 1000
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=90
            )
            result = response.json()['choices'][0]['message']['content']
            
            # 后处理保险：强制过滤Markdown符号
            result = (result
                     .replace('#', '')
                     .replace('**', '')
                     .replace('*', '•')
                     .replace('- ', '• ')
                     .replace('`', '')
                     .replace('>', '')
                     .replace('###', '')
                     .replace('##', '')
                     .replace('__', ''))
            
            return result
            
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
            self.send_feishu("📭 今日CNS无生物医学相关新文，或RSS抓取失败")
            return
        
        report = f"📊 扫描 {len(self.journals)} 本顶刊，精选 {len(papers)} 篇\n\n"
        
        for i, paper in enumerate(papers, 1):
            analysis = self.deep_analysis(paper)
            report += f"━━━━━━━━━━━━\n【{i}】{paper['journal']} | {paper['title'][:50]}...\n{analysis}\n\n"
        
        self.send_feishu(report)
        print(f"CNS推送完成，共{len(papers)}篇")
    
    def send_feishu(self, text):
        if not self.feishu_url:
            print("未配置飞书")
            return
            
        payload = {
            "msg_type": "text",
            "content": {"text": f"🏆 CNS晨读 | {datetime.now().strftime('%m-%d')}\n\n{text}"}
        }
        requests.post(self.feishu_url, json=payload)

if __name__ == '__main__':
    analyzer = CNSAnalyzer()
    analyzer.run()
