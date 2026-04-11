import os
import json
import urllib.request
import urllib.parse
import streamlit as st
from typing import Tuple, List


class NaverNewsHandler:
    def __init__(self):
        self.client_id = ""
        self.client_secret = ""
        if hasattr(st, "secrets"):
            if "NAVER_CLIENT_ID" in st.secrets:
                self.client_id = st.secrets["NAVER_CLIENT_ID"]
            if "NAVER_CLIENT_SECRET" in st.secrets:
                self.client_secret = st.secrets["NAVER_CLIENT_SECRET"]
        if not self.client_id:
            self.client_id = os.getenv("NAVER_CLIENT_ID", "")
        if not self.client_secret:
            self.client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
        self.base_url = "https://openapi.naver.com/v1/search/news.json"

    def test_connection(self) -> Tuple[bool, str]:
        if not self.client_id or not self.client_secret:
            return False, "네이버 API 키 미설정"
        try:
            result, err = self.search("테스트", display=1)
            if err:
                return False, f"네이버 연결 실패: {err}"
            return True, "네이버 뉴스 연결 성공"
        except Exception as e:
            return False, f"네이버 연결 실패: {e}"

    def search(self, query: str, display: int = 10, sort: str = "date") -> Tuple[List[dict], str]:
        if not self.client_id or not self.client_secret:
            return [], "네이버 API 키가 설정되지 않았습니다"
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"{self.base_url}?query={encoded_query}&display={display}&sort={sort}"
            req = urllib.request.Request(url)
            req.add_header("X-Naver-Client-Id", self.client_id)
            req.add_header("X-Naver-Client-Secret", self.client_secret)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                items = data.get("items", [])
                results = []
                for item in items:
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
                    desc = item.get("description", "").replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
                    results.append({
                        "title": title,
                        "description": desc,
                        "link": item.get("originallink", item.get("link", "")),
                        "pubDate": item.get("pubDate", "")
                    })
                return results, None
        except urllib.error.HTTPError as e:
            return [], f"HTTP {e.code}"
        except Exception as e:
            return [], str(e)

    def search_trending_topics(self, keywords: List[str] = None, display_per_keyword: int = 5) -> List[dict]:
        if keywords is None:
            keywords = ["경제 위기", "부동산 폭락", "물가 상승", "실업률", "주식 폭등", "사회 이슈", "기후 변화", "인구 감소", "AI 일자리", "금리 인상"]
        all_results = []
        seen_titles = set()
        for kw in keywords:
            items, err = self.search(kw, display=display_per_keyword, sort="date")
            if err:
                continue
            for item in items:
                short_title = item["title"][:30]
                if short_title not in seen_titles:
                    seen_titles.add(short_title)
                    item["keyword"] = kw
                    all_results.append(item)
        return all_results
