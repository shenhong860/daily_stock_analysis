import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import argparse
import re

class GitHubTrendingAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        self.model = os.getenv('OPENAI_MODEL', 'deepseek-reasoner')
        self.feishu_url = os.getenv('GITHUB_FEISHU_URL')
        
    def fetch_trending(self, language):
        """抓取 GitHub Trending 页面"""
        url = f"https://github.com/trending/{language}?since=daily"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            repos = []
            # GitHub trending 页面结构
            articles = soup.find_all('article', class_='Box-row')
            
            for article in articles[:5]:  # 前5个
                # 提取仓库名
                h2 = article.find('h2')
                if not h2:
                    continue
                    
                repo_name = h2.get_text(strip=True).replace(' ', '')
                
                # 提取描述
                p = article.find('p', class_='col-9')
                description = p.get_text(strip=True) if p else "暂无描述"
                
                # 提取星星数
                stars_span = article.find('span', class_='d-inline-block')
                stars = "未知"
                if stars_span:
                    stars_text = stars_span.get_text(strip=True)
                    match = re.search(r'([\d,]+)', stars_text)
                    if match:
                        stars = match.group(1)
                
                # 提取今日新增stars（如果有）
                today_stars = ""
                added_span = article.find('span', class_='d-inline-block', string=re.compile(r'today|stars today'))
                if added_span:
                    today_stars = added_span.get_text(strip=True)
                
                repos.append({
                    'name': repo_name,
                    'description': description,
                    'stars': stars,
                    'today_stars': today_stars,
                    'language': language,
                    'url': f"https://github.com/{repo_name}"
                })
                
            return repos
            
        except Exception as e:
            print(f"抓取 {language} 失败: {str(e)}")
            return []
    
    def analyze_repo(self, repo):
        """用 DeepSeek 分析仓库亮点"""
        prompt = f"""你是资深开源项目分析师，请用极简语言总结这个GitHub项目（限制总字数<150字）：

仓库：{repo['name']}
语言：{repo['language']}
描述：{repo['description']}
总Star：{repo['stars']} | 今日新增：{repo['today_stars']}

请输出：
💡 **一句话定位**：这是什么工具/库？（如："极简Python爬虫框架"）
🚀 **解决痛点**：解决了什么具体问题？（如："比Scrapy轻量10倍"）
🎯 **适合谁**：推荐给什么场景/人群？（如："适合快速抓取中小规模数据"）

输出格式示例：
💡 API性能测试工具 | 🚀 比Postman轻量，支持自动化压测 | 🎯 后端开发自测接口用
"""
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.5,
            'max_tokens': 400
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=30
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
🔥 **GitHub 今日热点** | {datetime.now().strftime('%Y-%m-%d')}

{content}

---
⭐ 数据来源：GitHub Trending | 由 DeepSeek-R1 速读
        """
        
        payload = {
            "msg_type": "text",
            "content": {
                "text": formatted
            }
        }
        
        requests.post(self.feishu_url, json=payload)
        print("GitHub Trending 推送成功")
    
    def run(self, languages_str):
        languages = [l.strip() for l in languages_str.split(',')]
        
        full_report = ""
        total_repos = 0
        
        for lang in languages:
            print(f"正在抓取 {lang} 榜单...")
            repos = self.fetch_trending(lang)
            
            if not repos:
                continue
                
            full_report += f"\n📌 **{lang.upper()}** 榜 Top {len(repos)}:\n\n"
            
            for i, repo in enumerate(repos, 1):
                print(f"  分析 {repo['name']}...")
                analysis = self.analyze_repo(repo)
                
                # 短格式输出
                full_report += f"{i}. **{repo['name']}** ⭐{repo['stars']}\n"
                full_report += f"   {analysis}\n"
                full_report += f"   🔗 {repo['url']}\n\n"
                
            total_repos += len(repos)
        
        if total_repos == 0:
            self.send_feishu("📭 今日 GitHub Trending 抓取失败或被反爬，请稍后重试")
            return
            
        self.send_feishu(full_report)
        print(f"完成！分析了 {total_repos} 个仓库")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--languages', default='python,typescript', help='编程语言列表')
    args = parser.parse_args()
    
    analyzer = GitHubTrendingAnalyzer()
    analyzer.run(args.languages)
