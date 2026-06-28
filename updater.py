# 파일 위치: trend-bubble-dashboard/updater.py
import os
import json
import time
import sys

# nlp_analyzer가 들어있는 backend 폴더 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import nltk
from nlp_analyzer import get_trends

# NLTK 리소스 다운로드
for resource in ['punkt', 'averaged_perceptron_tagger', 'maxent_ne_chunker', 'words', 'stopwords']:
    try:
        nltk.data.find(f'tokenizers/{resource}' if resource=='punkt' else f'corpora/{resource}')
    except LookupError:
        nltk.download(resource, quiet=True)

def update_json_files():
    print("최신 뉴스 수집 및 NLP 분석 시작...")
    for lang in ['en', 'ko']:
        try:
            trends = get_trends(lang)
            data_to_save = {
                'language': lang,
                'last_updated': time.time(),
                'count': len(trends),
                'trends': trends
            }
            # frontend 폴더 안에 저장해서 웹사이트가 바로 쓸 수 있게 해요
            output_path = f'frontend/data_{lang}.json'
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            print(f"[{lang}] 저장 완료 -> {output_path}")
        except Exception as e:
            print(f"[{lang}] 에러 발생: {e}")

if __name__ == '__main__':
    update_json_files()
