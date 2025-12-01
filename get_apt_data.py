import json
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

# 로컬 DB 사용 여부 확인 (SUPABASE_URL이 없으면 로컬 DB 사용)
def _check_use_local_db():
    if os.environ.get("SUPABASE_URL"):
        return False
    try:
        if st.secrets.get("SUPABASE_URL"):
            return False
    except (FileNotFoundError, KeyError):
        pass
    return True

USE_LOCAL_DB = _check_use_local_db()

if USE_LOCAL_DB:
    from local_db import supabase
else:
    from supabase import create_client, Client
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)


def get_apt_data(apt_display_name):
    """
    아파트 데이터를 가져오는 함수
    apt_display_name: "아파트이름 (평형평)" 형식의 문자열
    """
    try:
        # 표시 이름에서 실제 이름과 평형 추출
        # "아파트이름 (평형평)" 형식에서 마지막 괄호를 기준으로 파싱
        # 예: "래미안슈르(301~342동) (34평)" -> name: "래미안슈르(301~342동)", PY: "34"
        last_paren_idx = apt_display_name.rfind(" (")
        if last_paren_idx != -1:
            apt_name = apt_display_name[:last_paren_idx]
            PY = apt_display_name[last_paren_idx+2:].split("평")[0]
        else:
            # 폴백: 기존 방식
            apt_name = apt_display_name.split(" (")[0]
            PY = apt_display_name.split("(")[1].split("평")[0]
        
        def parse_price_trend(data):
            """price_trend를 파싱하는 헬퍼 함수 - 이미 리스트면 그대로 반환"""
            if data is None:
                return []
            if isinstance(data, list):
                return data
            if isinstance(data, str):
                return json.loads(data)
            return []

        # 매매 데이터 가져오기 (DEAL_TYPE = '1')
        response = supabase.table('APTInfo').select('*').eq('name', apt_name).eq('PY', PY).eq('DEAL_TYPE', '1').limit(1).single().execute()
        res1 = response.data
        dataset1 = parse_price_trend(res1['price_trend']) if res1 else []

        # 전세 데이터 가져오기 (DEAL_TYPE = '2')
        response = supabase.table('APTInfo').select('*').eq('name', apt_name).eq('PY', PY).eq('DEAL_TYPE', '2').limit(1).single().execute()
        res2 = response.data
        dataset2 = parse_price_trend(res2['price_trend']) if res2 else []

        # 월세 데이터 가져오기 (DEAL_TYPE = '3')
        response = supabase.table('APTInfo').select('*').eq('name', apt_name).eq('PY', PY).eq('DEAL_TYPE', '3').limit(1).single().execute()
        res3 = response.data
        dataset3 = parse_price_trend(res3['price_trend']) if res3 else []
        
        return apt_name, PY, dataset1, dataset2, dataset3
        
    except Exception as e:
        print(f"아파트 데이터 조회 중 오류 발생: {e}")
        return None, None, [], [], []


# TODO: sqlalchemy로 SQL 부분 정리하기
def extract_and_save_year(description):
    """
    설명에서 준공년월을 추출하여 정수로 반환하는 함수
    예: "서울 중구 신당동 / 02년05월 / 5152세대 / 아파트" -> 200205
    """
    try:
        # '/' 로 분리하고 두 번째 항목 (년월 정보) 가져오기
        year_month_part = description.split('/')[1].strip()
        
        # "년"과 "월"을 기준으로 숫자만 추출
        year = year_month_part.split('년')[0].strip()
        month = year_month_part.split('년')[1].split('월')[0].strip()
        
        # 2자리 연도를 4자리로 변환
        year = '19' + year if int(year) > 50 else '20' + year
        
        # 월이 한 자리인 경우 앞에 0 추가
        month = month.zfill(2)
        
        return int(year + month)
    except Exception as e:
        print(f"년월 추출 중 오류 발생: {e}")
        return None

def update_apt_year():
    """
    APTInfo 테이블의 모든 레코드를 순회하면서 
    description에서 준공년월을 추출하여 year 필드에 업데이트
    """
    try:
        # 모든 고유한 description 가져오기
        response = supabase.table('APTInfo').select('id, description').execute()
        records = response.data
        
        # 각 레코드 업데이트
        for record in records:
            if record['description']:
                year = extract_and_save_year(record['description'])
                if year:
                    # year 필드 업데이트
                    supabase.table('APTInfo').update({'year': year}).eq('id', record['id']).execute()
        
        print("준공년월 업데이트 완료")
    except Exception as e:
        print(f"데이터베이스 업데이트 중 오류 발생: {e}")

def get_apt_list():
    """
    아파트 목록을 name, year, PY, address와 함께 반환하는 함수
    """
    try:
        data = supabase.table('APTInfo').select('name, year, PY, address').execute().data
        # 중복 제거 및 정렬 (이름과 평형을 함께 고려)
        unique_apts = {}
        for d in data:
            # 이름과 평형을 함께 키로 사용
            key = f"{d['name']}_{d['PY']}"
            if key not in unique_apts or d.get('year', 0) < unique_apts[key].get('year', float('inf')):
                unique_apts[key] = {
                    'name': f"{d['name']} ({d['PY']}평)",  # 표시될 때는 평형 정보 포함
                    'original_name': d['name'],  # 원래 이름은 따로 저장
                    'year': d.get('year', 0),
                    'PY': d['PY'],
                    'address': d.get('address', '')  # 주소 정보 추가
                }
        
        # 이름순으로 정렬된 리스트 반환
        return sorted(unique_apts.values(), key=lambda x: x['name'])
    except Exception as e:
        print(f"아파트 목록 조회 중 오류 발생: {e}")
        return []

def extract_address(description):
    """
    설명에서 주소 정보를 추출하는 함수
    예: "서울 중구 신당동 / 02년05월  / 5152세대 / 아파트" -> "서울 중구"
    예: "경기 수원시 영통구 원천동 / 19년05월  / 2231세대 / 아파트" -> "수원시 영통구"
    """
    try:
        # 첫 번째 '/' 이전의 주소 부분 추출
        address_part = description.split('/')[0].strip()
        parts = address_part.split()
        
        if parts[0] == '서울':
            # 서울의 경우: '서울 구'
            address = f"{parts[0]} {parts[1]}"
        elif parts[0] == '경기':
            # 경기의 경우: '시 구'
            address = f"{parts[1]} {parts[2]}"
        else:
            # 그 외의 경우 처리
            address = f"{parts[1]} {parts[2]}"
        
        return address
    except Exception as e:
        print(f"주소 추출 중 오류 발생: {e}")
        return None

def update_apt_address():
    """
    APTInfo 테이블의 모든 레코드를 순회하면서 
    description에서 주소를 추출하여 address 필드에 업데이트
    """
    try:
        # 모든 고유한 description 가져오기
        response = supabase.table('APTInfo').select('id, description').execute()
        records = response.data
        
        # 각 레코드 업데이트
        for record in records:
            if record['description']:
                address = extract_address(record['description'])
                if address:
                    # address 필드 업데이트
                    supabase.table('APTInfo').update({'address': address}).eq('id', record['id']).execute()
        
        print("주소 정보 업데이트 완료")
    except Exception as e:
        print(f"데이터베이스 업데이트 중 오류 발생: {e}")
