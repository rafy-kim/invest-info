import streamlit as st
import pandas as pd
import altair as alt
from urllib.error import URLError
from get_apt_data import get_apt_data, get_apt_list

# 자동 리렌더링 방지
st.set_page_config(page_title="아파트", page_icon="🏢")

st.markdown("# 아파트")
st.sidebar.header("아파트")
# st.write(
#     """This demo shows how to use `st.write` to visualize Pandas DataFrames.
# (Data courtesy of the [UN Data Explorer](http://data.un.org/Explorer.aspx).)"""
# )


@st.cache_data
def load_data(dataset1, dataset2):
    # 데이터프레임 생성
    df1 = pd.DataFrame(dataset1)
    df2 = pd.DataFrame(dataset2)

    # 빈 데이터셋 처리
    if df1.empty and df2.empty:
        return pd.DataFrame(columns=['Date', '매매가', '매매 거래량', '월세', '월세 거래량', 'PER'])

    # 매매 데이터 처리
    if not df1.empty:
        df1['date'] = pd.to_datetime(df1['date'], format='%Y%m')
        df1 = df1.rename(columns={
            'date': 'Date',
            'avg': '매매가',
            'cnt': '매매 거래량'
        })
        df1['Date'] = df1['Date'].dt.date
    else:
        df1 = pd.DataFrame(columns=['Date', '매매가', '매매 거래량'])

    # 월세 데이터 처리
    if not df2.empty:
        df2['date'] = pd.to_datetime(df2['date'], format='%Y%m')
        df2 = df2.rename(columns={
            'date': 'Date',
            'avg': '월세',
            'cnt': '월세 거래량'
        })
        df2['Date'] = df2['Date'].dt.date
    else:
        df2 = pd.DataFrame(columns=['Date', '월세', '월세 거래량'])

    # Date를 기준으로 병합
    if df1.empty:
        df3 = df2.copy()
        df3['매매가'] = 0
        df3['매매 거래량'] = 0
    elif df2.empty:
        df3 = df1.copy()
        df3['월세'] = 0
        df3['월세 거래량'] = 0
    else:
        df3 = pd.merge(df1, df2, on='Date', how='outer')

    df3 = df3.sort_values(by='Date')

    # 결측치를 이전 달 값으로 채워넣기
    df3['매매가'] = df3['매매가'].astype(float).ffill()
    df3['월세'] = df3['월세'].astype(float).ffill()
    df3 = df3.fillna(0)

    # 'PER' 계산 (월세가 0인 경우 inf 방지)
    df3['PER'] = df3.apply(lambda row: row['매매가'] / (row['월세'] * 12) if row['월세'] > 0 else 0, axis=1)

    return df3

try:
    # 전체 아파트 목록 가져오기
    apt_list = get_apt_list()
    
    # 사이드바에 필터 추가
    st.sidebar.subheader("필터")
    
    # 지역 목록 가져오기
    addresses = sorted({apt.get('address', '') for apt in apt_list if apt.get('address')})
    
    # 기본 선택될 지역들
    default_addresses = [
        # '서울 강남구',
        # '서울 서초구',
        '서울 송파구',
        # '서울 성동구'
    ]
    # 실제 존재하는 지역만 기본값으로 설정
    default_selections = [addr for addr in default_addresses if addr in addresses]
    
    # 지역 선택 (다중 선택 가능)
    selected_addresses = st.sidebar.multiselect(
        "지역",
        options=addresses,
        default=default_selections,  # 기본값을 4개 지역으로 설정
        help="지역을 선택하세요. 여러 지역을 선택할 수 있습니다."
    )
    
    # 현재 년도 계산 (동적)
    from datetime import datetime
    current_year = datetime.now().year

    # 준공년도 범위 계산 (경과 연수로 변환)
    years = sorted({apt['year'] for apt in apt_list if apt.get('year')})
    years = [y//100 for y in years if y]  # 년도만 추출 (예: 202312 -> 2023)

    if years:
        min_elapsed = current_year - max(years)  # 최소 경과 연수 (미래 준공 포함시 음수 가능)
        min_elapsed = min(0, min_elapsed)  # 미래 준공 아파트 포함 (-1년 등)
        max_elapsed = current_year - min(years)  # 최대 경과 연수
    else:
        min_elapsed = -1
        max_elapsed = 50

    # 경과 연수 선택 슬라이더
    elapsed_years = st.sidebar.slider(
        "준공 경과 연수",
        min_value=min_elapsed,
        max_value=max_elapsed,
        value=(min_elapsed, 10),  # 기본값: 미래~10년
        step=1,
        format="%d년"
    )

    # 선택된 경과 연수를 실제 연도로 변환
    selected_max_year = current_year - elapsed_years[0]
    selected_min_year = current_year - elapsed_years[1]
    
    # 평수 범위 계산
    PYs = sorted({float(apt['PY']) for apt in apt_list if apt.get('PY')})
    min_PY = min(PYs) - 1 if PYs else 0
    max_PY = max(PYs) + 1 if PYs else 100
    
    # 평수 선택 슬라이더
    PY_range = st.sidebar.slider(
        "평수",
        min_value=float(min_PY),
        max_value=float(max_PY),
        value=(float(min_PY), float(max_PY)),
        format="%.1f평"
    )
    
    # 필터링된 아파트 목록 생성 (지역, 경과 연수, 평수 기준으로 필터링)
    filtered_apts = [
        apt for apt in apt_list
        if (apt.get('address', '') in selected_addresses) and  # 지역 필터
        (selected_min_year <= apt.get('year', 0) // 100 <= selected_max_year) and  # 경과 연수 필터 (년도만 비교)
        (PY_range[0] <= float(apt.get('PY', 0)) <= PY_range[1])  # 평수 필터
    ]
    
    # 필터링된 아파트 이름 목록
    apt_names = [apt['name'] for apt in filtered_apts]
    
    # 아파트 선택
    apt = st.selectbox("Choose a APT", apt_names)
    
    if not apt:
        st.error("Please select a APT.")
    else:
        # 선택된 아파트 데이터 로드
        apt_name, apt_PY, dataset1, dataset2, dataset3 = get_apt_data(apt)
        df = load_data(dataset1, dataset3)
        
        # 기간 선택 슬라이더 (아파트 선택 후 표시)
        start_date, end_date = st.sidebar.select_slider(
            '조회하고 싶은 기간을 선택하세요',
            options=df["Date"].tolist(),
            value=(df["Date"].min(), df["Date"].max())
        )
        df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
        
        # 차트 그리기
        st.write(f"### {apt_name} - {apt_PY}평")

        # 데이터가 있는 경우에만 차트 표시
        if not df.empty and len(df) > 0:
            # PER 평균 미리 계산 (동적 계산 방지)
            avg_per = df['PER'].mean() if df['PER'].sum() > 0 else 0

            line_chart1 = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("매매가:Q", title="매매가"),
                color=alt.value('red'),
            )

            line_chart2 = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("PER:Q", title="PER"),
                color=alt.value('blue'),
            )

            # 수평선 추가 (미리 계산된 값 사용)
            hline1 = alt.Chart(pd.DataFrame({'y': [avg_per]})).mark_rule(color='orange', strokeWidth=1).encode(y='y:Q')
            hline2 = alt.Chart(pd.DataFrame({'y': [35]})).mark_rule(color='yellow', strokeWidth=1).encode(y='y:Q')
            hline3 = alt.Chart(pd.DataFrame({'y': [30]})).mark_rule(color='green', strokeWidth=1).encode(y='y:Q')

            # 차트에 수평선 추가
            base_chart = alt.layer(line_chart2, hline1, hline2, hline3).resolve_scale()
            # 전체 차트 그리기
            final_chart = alt.layer(line_chart1, base_chart).resolve_scale(y='independent')
            st.altair_chart(final_chart, use_container_width=True)
        else:
            st.warning("표시할 데이터가 없습니다.")

        # 데이터가 있는 경우에만 통계 및 테이블 표시
        if not df.empty and len(df) > 0:
            df_display = df.set_index('Date').copy()

            # 최근 6개월 매매가 평균
            avg_price = df_display[-6:]['매매가'].mean() if len(df_display) > 0 else 0
            st.write(f"- 최근 6개월 매매가 평균: {round(avg_price/10000, 1)}억원")

            # 최근 6개월 월세 평균
            avg_rent = df_display[-6:]['월세'].mean() if len(df_display) > 0 else 0
            st.write(f"- 최근 6개월 월세 평균: {int(avg_rent)}만원")

            # 최근 월세 시세를 통해 추정한 기대 매매가
            if avg_rent > 0:
                s_val = avg_rent * 12 * 30
                e_val = avg_rent * 12 * 35
                st.write(f"- 최근 월세 시세를 통해 추정한 기대 매매가: :blue[{round(s_val/10000, 1)}억원] ~ :blue[{round(e_val/10000, 1)}억원]")
            else:
                st.write("- 최근 월세 시세를 통해 추정한 기대 매매가: 월세 데이터 없음")

            st.divider()

            st.dataframe(df_display, use_container_width=True)



except URLError as e:
    st.error(
        """
        **This demo requires internet access.**
        Connection error: %s
    """
        % e.reason
    )




