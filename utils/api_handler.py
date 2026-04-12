import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from utils.skywork_handler import SkyworkHandler
from utils.kie_handler import KieHandler
from utils.inworld_handler import InworldHandler
from utils.naver_news_handler import NaverNewsHandler


class APIHandler:
    def __init__(self):
        self.skywork = SkyworkHandler()
        self.kie = KieHandler()
        self.inworld = InworldHandler()
        self.naver = NaverNewsHandler()

    def test_all(self):
        results = {}
        ok, msg = self.skywork.test_connection()
        results["skywork"] = (ok, msg)
        ok, msg = self.naver.test_connection()
        results["naver"] = (ok, msg)
        kie_ok = bool(self.kie.api_key)
        kie_msg = "Kie AI 키 설정됨" if kie_ok else "Kie AI 키 미설정"
        results["kie"] = (kie_ok, kie_msg)
        ok, msg = self.inworld.test_connection()
        results["inworld"] = (ok, msg)
        return results

    def test_connection(self):
        r = self.test_all()
        all_ok = all(v[0] for v in r.values())
        combined = "\n".join(f"{k}: {v[1]}" for k, v in r.items())
        return all_ok, combined

    def generate(self, prompt, max_tokens=8192):
        return self.skywork.generate(prompt, max_tokens)

    def generate_long(self, prompt):
        return self.skywork.generate_long(prompt)

    def generate_long_with_search(self, prompt):
        return self.skywork.generate_long_with_search(prompt)

    def generate_image(self, prompt, aspect_ratio="9:16"):
        return self.skywork.generate_image(prompt, aspect_ratio)

    def download_image(self, file_url, save_path):
        return self.skywork.download_image(file_url, save_path)
