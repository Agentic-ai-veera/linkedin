import json
import os
from dotenv import load_dotenv
import requests
from langchain.tools import tool
from bs4 import BeautifulSoup
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import re
from typing import Optional
from serpapi.google_search import GoogleSearch
import html2text
from pydantic import BaseModel
import time

# Load environment variables
load_dotenv()

class SearchTools:
    def __init__(self):
        self.serpapi_key = os.getenv("SERPAPI_API_KEY")
        if not self.serpapi_key:
            raise ValueError("SERPAPI_API_KEY not found in environment variables")
        
    @staticmethod
    def _clean_html(html_content: str) -> str:
        """Convert HTML to clean text"""
        h = html2text.HTML2Text()
        h.ignore_links = False
        return h.handle(html_content)

    @tool("serp_api_search")
    def _search_serpapi(self, query: str) -> list:
        """Search using SerpAPI with rate limiting"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                params = {
                    "engine": "google",
                    "q": query,
                    "api_key": self.serpapi_key,
                    "num": 5,
                    "tbm": "nws"  # For news results
                }
                response = requests.get("https://serpapi.com/search", params=params)
                results = response.json()
                if "news_results" not in results:
                    return []
                return [{
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'source': item.get('source', ''),
                    'date': item.get('date', '')
                } for item in results["news_results"]]
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit error
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"SerpAPI error: {str(e)}")
                    return []
        print("Max retries exceeded.")
        return []

    def _get_google_news(self, query: str, max_results: int = 5) -> list:
        """Get news from Google News RSS feed"""
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            
            feed = feedparser.parse(url)
            
            results = []
            for entry in feed.entries[:max_results]:
                results.append({
                    'title': entry.title,
                    'link': self._clean_url(entry.link),
                    'summary': entry.get('summary', ''),
                    'published': entry.published
                })
            
            return results
        except Exception as e:
            print(f"Google News error: {str(e)}")
            return []
        
    @tool("medium_article_summary")
    def medium_article_summary(self, url: str) -> str:
        """Extract and summarize the content of a specific Medium article. Input: article URL string"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            # Remove unwanted elements
            for element in soup.select('script, style, nav, footer, header, aside'):
                element.decompose()
            # Extract main content
            article_content = ""
            content_selectors = [
                'article', '.article-content', '.post-content',
                '[role="main"]', '.main-content', '#content'
            ]
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    article_content = content.get_text(separator='\n', strip=True)
                    break
            if not article_content:
                paragraphs = soup.find_all('p')
                article_content = '\n'.join(p.get_text(strip=True) for p in paragraphs)
            return article_content[:2000] + "..." if len(article_content) > 2000 else article_content
        except Exception as e:
            return f"Error browsing: {str(e)}"

    def _search_medium(self, query: str, max_results: int = 5) -> list:
        """Search Medium blogs"""
        try:
            # Medium's search URL
            encoded_query = urllib.parse.quote(query)
            url = f"https://medium.com/search?q={encoded_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            articles = []
            # Find article elements (adjust selectors based on Medium's current structure)
            for article in soup.select('article')[:max_results]:
                title_elem = article.select_one('h2')
                link_elem = article.select_one('a[href*="/p/"]')
                excerpt_elem = article.select_one('p')
                
                if title_elem and link_elem:
                    articles.append({
                        'title': title_elem.text.strip(),
                        'link': f"https://medium.com{link_elem['href']}",
                        'excerpt': excerpt_elem.text.strip() if excerpt_elem else ''
                    })
            
            return articles
            
        except Exception as e:
            print(f"Medium search error: {str(e)}")
            return []

    @staticmethod
    def _clean_url(url: str) -> str:
        """Clean and extract actual URL from Google News URL"""
        if 'news.google.com' in url:
            match = re.search(r'url=([^&]+)', url)
            if match:
                return urllib.parse.unquote(match.group(1))
        return url

    @tool("Search internet")
    def search_internet(self, query: str) -> str:
        """Search for trending tech news using multiple sources"""
        try:
            results = {
                'serp_results': self._search_serpapi(query),
                'google_news': self._get_google_news(query),
                'medium_blogs': self._search_medium(query)
            }
            
            # Format results nicely
            formatted_results = []
            
            # Add SerpAPI results
            if results['serp_results']:
                formatted_results.append("\n=== SERP RESULTS ===")
                for idx, item in enumerate(results['serp_results'], 1):
                    formatted_results.append(f"\n{idx}. {item['title']}")
                    formatted_results.append(f"Source: {item['source']}")
                    formatted_results.append(f"Date: {item['date']}")
                    formatted_results.append(f"URL: {item['link']}")
                    formatted_results.append(f"Summary: {item['snippet']}\n")
            
            # Add Google News results
            if results['google_news']:
                formatted_results.append("\n=== GOOGLE NEWS ===")
                for idx, item in enumerate(results['google_news'], 1):
                    formatted_results.append(f"\n{idx}. {item['title']}")
                    formatted_results.append(f"Published: {item['published']}")
                    formatted_results.append(f"URL: {item['link']}")
                    formatted_results.append(f"Summary: {item['summary']}\n")
            
            # Add Medium blog results
            if results['medium_blogs']:
                formatted_results.append("\n=== MEDIUM BLOGS ===")
                for idx, item in enumerate(results['medium_blogs'], 1):
                    formatted_results.append(f"\n{idx}. {item['title']}")
                    formatted_results.append(f"URL: {item['link']}")
                    formatted_results.append(f"Excerpt: {item['excerpt']}\n")
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            return f"Error searching: {str(e)}"

    @staticmethod
    @tool("Search instagram")
    def search_instagram(query: str) -> str:
        """Search for Instagram posts about a topic"""
        try:
            modified_query = f"site:instagram.com {query} latest"
            return SearchTools.search_internet(modified_query)
        except Exception as e:
            return f"Error searching Instagram: {str(e)}"

    @tool("generate_image")
    def generate_image(self, prompt: str, save_path: str) -> str:
        """Generate an image using the Inference API based on the provided prompt."""
        api_url = "https://api.stability.ai/v1/generate"  # Replace with the actual API endpoint
        headers = {
            "Authorization": f"Bearer {os.getenv('STABILITY_API_KEY')}",  # Ensure you have your API key set in environment variables
            "Content-Type": "application/json"
        }
        data = {
            "prompt": prompt,
            "num_images": 1,  # Number of images to generate
            "size": "512x512"  # Specify the size of the image
        }
        
        response = requests.post(api_url, headers=headers, json=data)
        
        if response.status_code == 200:
            image_data = response.json()
            image_url = image_data['images'][0]['url']  # Adjust based on the actual response structure
            # Download the image
            img_response = requests.get(image_url)
            with open(save_path, 'wb') as f:
                f.write(img_response.content)
            return f"Image saved as: {save_path}"
        else:
            return f"Error generating image: {response.text}"