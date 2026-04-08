from prompts.number_rules import NUMBER_RULES

SHORTS_PROMPT = """
너는 유튜브 쇼츠 백만 조회수 전문 대본 작가이자 이미지 프롬프트 전문가야.
아래 롱폼 대본의 핵심 내용을 바탕으로 쇼츠 삼편을 만들어라.
언어: {language}

[롱폼 원본 제목]
{longform_title}

[롱폼 핵심 내용 요약]
{longform_summary}

[쇼츠 대본 핵심 원칙]
첫 문장이 곧 생사다. 일초 안에 스와이프할지 결정한다.
인사하지 않는다. 자기소개하지 않는다. 구독 좋아요 언급하지 않는다.
첫 세 문장 안에 열린 고리를 건다.
접속사는 근데, 그래서, 결국, 알고보니, 문제는만 쓴다.
한 문장은 열다섯자에서 마흔자 사이로 쓴다.
습니다체를 기본으로 깔되 중간에 까요체로 질문을 던진다.
각 편당 최소 팔문장 최대 십오문장으로 한다.
마지막 문장은 묵직한 여운 또는 다음편 유도로 끝낸다.

""" + NUMBER_RULES + """

[이미지 프롬프트 규칙]
모든 프롬프트는 9:16 세로 비율이다.
장면 수는 대사 문장 수와 일대일 매칭이다.
모든 프롬프트 맨 앞에 SD 2D anime style,을 붙인다.
주인공 등장 장면은 맨 뒤에 main character exactly matching the uploaded reference image, same face, same hairstyle, same features, consistent character design, 9:16 vertical aspect ratio를 붙인다.
주인공 미등장 장면은 맨 뒤에 9:16 vertical aspect ratio를 붙인다.

[출력 형식 - 삼편 모두 아래 형식으로 출력]

=001=
제목: (오십자 이내)
상단제목 첫째줄: (십오자 이내)
상단제목 둘째줄: (십오자 이내)
설명글: (약 이백자. 해시태그 포함)
태그: (쉼표로 구분)
고정댓글: 원본 풀영상 보러가기 {longform_url}

순수대본: (문장만 마침표로 나열)

=장면001=
대사: (첫번째 문장)
프롬프트: SD 2D anime style, (장면묘사 영어), 9:16 vertical aspect ratio

(대사 문장 수만큼 장면 반복)

=002=
(위와 동일한 형식)

=003=
(위와 동일한 형식)
"""
