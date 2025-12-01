import streamlit as st
from dotenv import load_dotenv
import os
import pandas as pd
from get_apt_data import get_apt_data, get_apt_list, supabase

st.set_page_config(
    page_title="Home",
    page_icon="📊",
)

st.write("# 아파트 PER ")
# st.markdown("# 아파트 PER LIST")
# st.sidebar.header("주요 아파트들의 최근 PER")

# st.sidebar.success("메뉴를 골라주세요")
st.markdown(
    """
주요 아파트들의 최근 PER 값을 기준으로 낮은 순으로 표시합니다.
    """
)

response = supabase.table('APTLastPER').select('*').execute()
print(response)

df = pd.DataFrame(response.data)

# df['updated'] = pd.to_datetime(df['updated'], format='%Y-%m-%dT%H:%M:%S.%f%z').dt.strftime('%Y-%m-%d')
df['updated'] = pd.to_datetime(df['updated'], format='ISO8601').dt.strftime('%Y-%m-%d')
df = df.drop(columns='id')
df = df.drop(columns='apt_id')

new_order = ['last_PER', 'apt_name', 'apt_PY', 'last_avg_price', 'last_avg_rent', 'updated']
df = df[new_order]

df = df.rename(columns={
    'last_PER': '최근 PER',
    'apt_name': '아파트',
    'apt_PY': '평형',
    'last_avg_price': '매매가',
    'last_avg_rent': '월세',
    'updated': '수정일',
})

# df['updated_date'] = pd.to_datetime(df['updated']).dt.date
df = df.set_index('최근 PER').sort_index()

st.dataframe(df, use_container_width=True)

