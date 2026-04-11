import os
import streamlit as st

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

    def test_connection(self):
        sk_ok, sk_msg = self.skywork.test_connection()
        iw_ok, iw_msg = self.inworld.test_connection()
        nv_ok, nv_msg = self.naver.test_connection()
        kie_key = self.kie.api_key
        kie_ok = bool(kie_key and "여기에" not in kie_key)
        kie_msg = "Kie AI 키 설정됨" if kie_ok else "Kie AI 키 미설정"
        combined = f"스카이워크: {sk_msg}\n인월드: {iw_msg}\nKie: {kie_msg}\n네이버: {nv_msg}"
        all_ok = sk_ok and iw_ok and nv_ok and kie_ok
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
