import streamlit as st
import json
from datetime import datetime, timedelta
from get_apt_data import get_apt_list, supabase
from apt_value import get_APT_info, get_APT_transactions

st.set_page_config(page_title="아파트 관리", page_icon="")

st.markdown("# 아파트 관리")
st.sidebar.header("아파트 관리")

# 탭 생성
tab1, tab2 = st.tabs(["아파트 추가", "아파트 삭제"])


def search_apt_from_asil(apt_name):
    """아실에서 아파트 검색"""
    import requests
    try:
        r = requests.get(f'https://asil.kr/json/getAptname_ver_3_4.jsp?os=pc&aptname={apt_name}')
        results = r.json()
        return results
    except Exception as e:
        st.error(f"아실 검색 오류: {e}")
        return []


def get_available_py_list(apt_info):
    """아파트의 사용 가능한 평형 목록 조회"""
    import requests
    import re
    try:
        seq = apt_info['seq']

        # 아실 apt_info 페이지에서 평형 정보 가져오기
        url = f"https://asil.kr/app/apt_info.jsp?os=pc&apt={seq}"
        r = requests.get(url)

        # search3(0, '39', '18') 패턴에서 평형(세 번째 파라미터) 추출
        # 첫번째: 전용면적(m²), 두번째: 평형
        py_pattern = r"search3\(\d+,\s*'\d+',\s*'(\d+)'\)"
        matches = re.findall(py_pattern, r.text)

        # 중복 제거 및 정렬
        unique_pys = sorted(set(matches), key=lambda x: int(x))

        return unique_pys
    except Exception as e:
        st.error(f"평형 조회 오류: {e}")
        return []


def collect_apt_data(apt_info, PY, progress_bar=None, status_text=None):
    """아파트 데이터 수집 및 DB 저장"""
    results = []

    # 오늘 날짜 기준 3년 전부터 수집
    today = datetime.today()
    start_year = today.year - 3

    deal_types = [('1', '매매'), ('2', '전세'), ('3', '월세')]
    total_steps = len(deal_types)

    for idx, (deal_type, deal_name) in enumerate(deal_types):
        if status_text:
            status_text.text(f"{deal_name} 데이터 수집 중...")

        price_trend = []

        # 3년치 데이터 수집
        for year in range(start_year, today.year + 1):
            try:
                amount = get_APT_transactions(apt_info, PY, str(year), deal_type)
                if amount:
                    price_trend.extend(amount)
            except Exception as e:
                st.warning(f"{year}년 {deal_name} 데이터 수집 실패: {e}")

        # 날짜순 정렬
        price_trend = sorted(price_trend, key=lambda x: x['date'])

        # DB에 저장
        try:
            # 기존 데이터 확인
            response = supabase.table('APTInfo').select('id').eq('name', apt_info['name']).eq('PY', PY).eq('DEAL_TYPE', deal_type).execute()

            # 주소 추출
            address = extract_address(apt_info['desc'])
            year_built = extract_year(apt_info['desc'])

            if response.data:
                # 기존 데이터 업데이트
                supabase.table('APTInfo').update({
                    'price_trend': json.dumps(price_trend),
                    'status': 1
                }).eq('id', response.data[0]['id']).execute()
            else:
                # 새 데이터 삽입
                supabase.table('APTInfo').insert({
                    'name': apt_info['name'],
                    'PY': PY,
                    'DEAL_TYPE': deal_type,
                    'seq': apt_info['seq'],
                    'description': apt_info['desc'],
                    'address': address,
                    'year': year_built,
                    'price_trend': json.dumps(price_trend),
                    'status': 1
                }).execute()

            results.append({
                'deal_type': deal_name,
                'count': len(price_trend),
                'success': True
            })
        except Exception as e:
            results.append({
                'deal_type': deal_name,
                'count': 0,
                'success': False,
                'error': str(e)
            })

        if progress_bar:
            progress_bar.progress((idx + 1) / total_steps)

    return results


def extract_address(description):
    """설명에서 주소 추출"""
    try:
        address_part = description.split('/')[0].strip()
        parts = address_part.split()

        if parts[0] == '서울':
            return f"{parts[0]} {parts[1]}"
        elif parts[0] == '경기':
            return f"{parts[1]} {parts[2]}"
        else:
            return f"{parts[1]} {parts[2]}"
    except:
        return None


def extract_year(description):
    """설명에서 준공년월 추출"""
    try:
        year_month_part = description.split('/')[1].strip()
        year = year_month_part.split('년')[0].strip()
        month = year_month_part.split('년')[1].split('월')[0].strip()
        year = '19' + year if int(year) > 50 else '20' + year
        month = month.zfill(2)
        return int(year + month)
    except:
        return None


def delete_apt_data(apt_name, PY):
    """아파트 데이터 삭제 (status를 0으로 변경)"""
    try:
        # APTInfo 테이블에서 status를 0으로 변경
        response = supabase.table('APTInfo').select('id').eq('name', apt_name).eq('PY', PY).execute()

        if response.data:
            for record in response.data:
                supabase.table('APTInfo').update({'status': 0}).eq('id', record['id']).execute()

            # APTLastPER 테이블에서도 삭제
            supabase.table('APTLastPER').select('id').eq('apt_name', apt_name).eq('apt_PY', PY).execute()
            # APTLastPER는 실제로 삭제하거나 유지할 수 있음

            return True
        return False
    except Exception as e:
        st.error(f"삭제 오류: {e}")
        return False


# 탭1: 아파트 추가
with tab1:
    st.subheader("새 아파트 추가")

    # 검색 입력
    search_name = st.text_input("아파트 이름 검색", placeholder="예: 래미안, 헬리오시티")

    if search_name:
        with st.spinner("아실에서 검색 중..."):
            search_results = search_apt_from_asil(search_name)

        if search_results:
            # 검색 결과를 선택 가능한 형태로 표시
            options = [f"{r['name']} - {r['desc']}" for r in search_results[:10]]
            selected = st.selectbox("검색 결과에서 선택", options, index=None, placeholder="아파트를 선택하세요")

            if selected:
                selected_idx = options.index(selected)
                selected_apt = search_results[selected_idx]

                st.info(f"**선택된 아파트:** {selected_apt['name']}\n\n**설명:** {selected_apt['desc']}")

                # 평형 목록 가져오기
                apt_info_for_py = {
                    'seq': selected_apt['seq'],
                    'desc': selected_apt['desc']
                }

                with st.spinner("평형 목록 조회 중..."):
                    py_list = get_available_py_list(apt_info_for_py)

                py_input = None
                if py_list:
                    # 평형 선택 (selectbox)
                    py_options = [f"{py}평" for py in py_list]
                    selected_py = st.selectbox("평형 선택", py_options, index=None, placeholder="평형을 선택하세요")

                    if selected_py:
                        py_input = selected_py.replace("평", "")
                else:
                    st.warning("평형 정보를 가져올 수 없습니다. 직접 입력해주세요.")
                    py_input = st.text_input("평형 입력 (숫자만)", placeholder="예: 34")

                if py_input:
                    # 이미 등록된 아파트인지 확인
                    existing = supabase.table('APTInfo').select('id, status').eq('name', selected_apt['name']).eq('PY', py_input).eq('status', 1).execute()

                    if existing.data:
                        st.warning(f"{selected_apt['name']} {py_input}평은 이미 등록되어 있습니다.")
                    else:
                        if st.button("아파트 추가 및 데이터 수집", type="primary"):
                            apt_info = {
                                'name': selected_apt['name'],
                                'seq': selected_apt['seq'],
                                'desc': selected_apt['desc']
                            }

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            with st.spinner("데이터 수집 중... (약 1-2분 소요)"):
                                results = collect_apt_data(apt_info, py_input, progress_bar, status_text)

                            status_text.empty()
                            progress_bar.empty()

                            # 결과 표시
                            st.success(f"{selected_apt['name']} {py_input}평 추가 완료!")

                            for r in results:
                                if r['success']:
                                    st.write(f"- {r['deal_type']}: {r['count']}건 수집")
                                else:
                                    st.write(f"- {r['deal_type']}: 실패 ({r.get('error', '알 수 없는 오류')})")

                            st.cache_data.clear()
        else:
            st.warning("검색 결과가 없습니다.")


# 탭2: 아파트 삭제
with tab2:
    st.subheader("아파트 삭제")

    # 현재 등록된 아파트 목록
    apt_list = get_apt_list()

    if apt_list:
        # 선택 가능한 목록 생성
        apt_options = [apt['name'] for apt in apt_list]

        with st.form(key="delete_form"):
            selected_apt = st.selectbox("삭제할 아파트 선택", apt_options, index=None, placeholder="아파트를 선택하세요")

            st.warning("삭제하면 이 아파트의 데이터가 비활성화됩니다.")

            submit_button = st.form_submit_button("삭제", type="primary")

            if submit_button and selected_apt:
                # 선택된 아파트 정보 찾기
                apt_info = next((apt for apt in apt_list if apt['name'] == selected_apt), None)
                if apt_info:
                    success = delete_apt_data(apt_info['original_name'], apt_info['PY'])
                    if success:
                        st.success(f"{apt_info['original_name']} {apt_info['PY']}평이 삭제되었습니다.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("삭제에 실패했습니다.")
            elif submit_button and not selected_apt:
                st.error("삭제할 아파트를 선택해주세요.")
    else:
        st.info("등록된 아파트가 없습니다.")


# 현재 등록된 아파트 목록 표시
st.divider()
st.subheader("현재 등록된 아파트 목록")

apt_list = get_apt_list()
if apt_list:
    import pandas as pd
    df = pd.DataFrame(apt_list)
    df = df[['original_name', 'PY', 'address', 'year']]
    df.columns = ['아파트명', '평형', '주소', '준공년월']
    df['준공년월'] = df['준공년월'].apply(lambda x: f"{str(x)[:4]}년 {str(x)[4:]}월" if x else "N/A")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("등록된 아파트가 없습니다.")
