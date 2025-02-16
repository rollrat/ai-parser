import requests
from bs4 import BeautifulSoup
import os
from typing import Dict, Any
import json
import datetime
import time

def get_dcinside_posts():
    # URL 설정
    url = "https://gall.dcinside.com/mgallery/board/lists/?id=tenbagger&exception_mode=recommend"
    
    # User-Agent 설정 (차단 방지)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # 웹페이지 요청
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 오류 발생시 예외 발생
        
        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 게시글 목록 찾기 (수정된 선택자 사용)
        posts = soup.select('tbody.listwrap2 td.gall_tit > a[href^="/mgallery"]')
        
        # 결과 저장할 리스트
        results = []
        
        # 각 게시글의 제목과 링크 추출
        for post in posts:
            title = post.text.strip()
            link = "https://gall.dcinside.com" + post['href']
            results.append({"title": title, "link": link})
        
        return results
        
    except requests.RequestException as e:
        print(f"에러 발생: {e}")
        return []

def chat_with_groq(message: str) -> Dict[Any, Any]:
    """
    Groq API를 사용하여 deepseek-r1-distill-llama-70b 모델과 대화하는 함수
    """
    api_key = "~"
    # api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY 환경 변수가 설정되지 않았습니다.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-r1-distill-llama-70b",
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Groq API 호출 중 에러 발생: {e}")
        return {}

def parse_analysis_to_json(analysis_text: str) -> list:
    """분석 결과 텍스트를 JSON 형식으로 파싱하는 함수"""
    results = []
    current_item = {}
    
    lines = analysis_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 번호로 시작하는 라인 처리 (예: "48. Score: 6/10")
        if line[0].isdigit() and 'Score:' in line:
            if current_item:
                results.append(current_item)
            current_item = {}
            # 번호 추출
            number = line.split('.')[0]
            current_item['number'] = int(number)
            # Score 추출
            score = line.split('Score:')[1].strip()
            current_item['score'] = int(score.split('/')[0])
        # 일반적인 "번:" 형식 처리
        elif line.endswith('번:'):
            if current_item:
                results.append(current_item)
            current_item = {'number': int(line[:-2])}
        elif line.startswith('Score:'):
            score = line.replace('Score:', '').strip()
            current_item['score'] = int(score.split('/')[0])
        elif line.startswith('Reason:'):
            reason = line.replace('Reason:', '').strip()
            current_item['reason'] = reason
            
    if current_item:  # 마지막 항목 추가
        results.append(current_item)
        
    return results

def main():
    # 게시글 정보 가져오기
    posts = get_dcinside_posts()
    
    # 각 게시글에 대해 Groq API로 분석 요청
    for post in posts:
        print(f"\n=== 게시글 분석 ===")
        print(f"제목: {post['title']}")
        
        prompt = f"다음 게시글 제목의 정보 유용성을 1-10 등급으로 평가해줘. 답변 형식: '등급: N - 한줄평가' 형식으로만 답변해줘: {post['title']}"
        response = chat_with_groq(prompt)

        
        if response and 'choices' in response:
            analysis = response['choices'][0]['message']['content']
            # <think> 태그 제거
            if '<think>' in analysis:
                analysis = analysis.split('</think>')[-1].strip()
            print(f"분석 결과: {analysis}")
        else:
            print("분석 실패")

def get_analysis_prompt(posts):
    """게시글 목록으로부터 분석 프롬프트를 생성하는 함수"""
    titles = "\n".join([f"{i+1}. {post['title']}" for i, post in enumerate(posts)])
    
    return f"""다음은 주식 관련 게시글 제목 목록입니다. 각 게시글의 정보 유용성을 1-10 등급으로 평가해주세요.
답변 형식에 강조 문구를 표시하지 말고 각 줄에 하나씩 주어진 대로 답변해줘.
각 Reason 항목은 한국어로 답변해줘.
답변 형식:
1번:
Score: N/10
Reason: 한줄평가 한국어로 답변해줘

2번:
Score: N/10
Reason: 한줄평가 한국어로 답변해줘
...

게시글 목록:
{titles}"""

def combine_analysis_results(posts, analysis_results):
    """게시글 정보와 분석 결과를 결합하는 함수"""
    final_results = []
    for post, analysis in zip(posts, analysis_results):
        final_results.append({
            "title": post['title'],
            "link": post['link'],
            "analysis": {
                "score": analysis['score'],
                "reason": analysis['reason']
            }
        })
    return final_results

def save_results_to_json(final_results):
    """분석 결과를 JSON 파일로 저장하는 함수"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_results_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    return filename

def print_analysis_results(final_results):
    """분석 결과를 콘솔에 출력하는 함수"""
    print("\n=== 전체 게시글 분석 결과 ===")
    for result in final_results:
        print(f"\n제목: {result['title']}")
        print(f"점수: {result['analysis']['score']}/10")
        print(f"평가: {result['analysis']['reason']}")

def send_to_discord(results: list, webhook_url: str) -> None:
    """분석 결과를 Discord로 전송하는 함수"""
    
    # 점수 기준으로 내림차순 정렬
    sorted_results = sorted(results, key=lambda x: x['analysis']['score'], reverse=True)
    
    # 메시지 생성
    messages = []
    for result in sorted_results:
        score = result['analysis']['score']
        emoji = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
        
        message = (
            f"{emoji} **{score}/10** | [{result['title']}]({result['link']})\n"
            f"└ {result['analysis']['reason']}"
        )
        messages.append(message)
    
    # 메시지를 10개씩 나누어 전송
    for i in range(0, len(messages), 10):
        chunk = messages[i:i + 10]
        payload = {
            "content": "\n\n".join(chunk)
        }
        
        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            time.sleep(1)  # API 제한 방지를 위한 지연
        except requests.RequestException as e:
            print(f"Discord webhook 전송 중 에러 발생: {e}")

def get_score_color(score: int) -> int:
    """점수에 따른 임베드 색상 반환"""
    if score >= 8:
        return 0x00ff00  # 초록색
    elif score >= 6:
        return 0xffff00  # 노란색
    else:
        return 0xff0000  # 빨간색

def main2():
    # 게시글 정보 가져오기
    posts = get_dcinside_posts()
    
    if not posts:
        print("게시글을 가져오는데 실패했습니다.")
        return
        
    # 분석 프롬프트 생성 및 API 호출
    prompt = get_analysis_prompt(posts)
    response = chat_with_groq(prompt)
    
    if response and 'choices' in response:
        analysis = response['choices'][0]['message']['content']
        if '<think>' in analysis:
            analysis = analysis.split('</think>')[-1].strip()
            
        analysis_results = parse_analysis_to_json(analysis)
        
        final_results = combine_analysis_results(posts, analysis_results)
        
        # JSON 파일로 저장
        filename = save_results_to_json(final_results)
        print(f"\n분석 결과가 {filename}에 저장되었습니다.")
        
        # Discord로 전송
        webhook_url = "~"
        send_to_discord(final_results, webhook_url)
        print("분석 결과가 Discord로 전송되었습니다.")
        
        # 콘솔에 결과 출력
        print_analysis_results(final_results)
    else:
        print("분석 실패")

if __name__ == "__main__":
    # main()  # 개별 분석
    main2()   # 일괄 분석
