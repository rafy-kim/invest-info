import json
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
import os
from get_apt_data import get_apt_list, get_apt_data

# Load environment variables from the .env file
load_dotenv()

# 로컬 DB 사용
from local_db import supabase


def load_data(dataset1, dataset2):
    # 데이터프레임 생성
    # 데이터 프레임 생성
    df1 = pd.DataFrame(dataset1)
    df2 = pd.DataFrame(dataset2)
    # 'date'를 datetime 형식으로 변환
    df1['date'] = pd.to_datetime(df1['date'], format='%Y%m')
    df1 = df1.rename(columns={
        'date': 'Date',
        'avg': '매매가',
        'cnt': '매매 거래량'
    })
    df1['Date'] = df1['Date'].dt.date
    df2['date'] = pd.to_datetime(df2['date'], format='%Y%m')
    df2 = df2.rename(columns={
        'date': 'Date',
        'avg': '월세',
        'cnt': '월세 거래량'
    })
    df2['Date'] = df2['Date'].dt.date

    # df1 = pd.DataFrame(list(dataset1.items()), columns=['Date', 'Data'])
    # df1[['매매가', '매매 거래량']] = pd.DataFrame(df1['Data'].tolist(), index=df1.index)
    # df1.drop('Data', axis=1, inplace=True)
    # df2 = pd.DataFrame(list(dataset2.items()), columns=['Date', 'Data'])
    # df2[['월세', '월세 거래량']] = pd.DataFrame(df2['Data'].tolist(), index=df2.index)
    # df2.drop('Data', axis=1, inplace=True)
    #
    # # 데이터프레임을 날짜로 정렬
    # df1['Date'] = pd.to_datetime(df1['Date'], format='%Y%m')
    # df1['Date'] = df1['Date'].dt.date
    # df2['Date'] = pd.to_datetime(df2['Date'], format='%Y%m')
    # df2['Date'] = df2['Date'].dt.date
    # df1 = df1.sort_values(by='Date')
    # df2 = df2.sort_values(by='Date')

    # Date를 기준으로 병합
    # df3 = pd.merge(df1, df2, on='Date', how='inner')
    df3 = pd.merge(df1, df2, on='Date', how='outer')
    df3 = df3.sort_values(by='Date')

    # 결측치를 이전 달 값으로 채워넣기
    df3['매매가'] = df3['매매가'].astype(float).ffill()
    df3['월세'] = df3['월세'].astype(float).ffill()
    df3 = df3.fillna(0)

    # 'PER' 계산
    df3['PER'] = df3['매매가'] / (df3['월세'] * 12)

    return df3


try:
    # cur = connection.cursor(DictCursor)
    # Create a cursor to interact with the database
    apts = get_apt_list()
    for apt in apts:
        apt_name, apt_PY, dataset1, dataset2, dataset3 = get_apt_data(apt['name'])
        df = load_data(dataset1, dataset3)
        df = df.set_index('Date')

        # df3 = df3.set_index('Date')
        # df3.index = df3.index.date

        # 최근 6개월 매매가 평균
        last_avg_price = round(df[-6:].mean()['매매가']/10000, 1)
        print(f"- 최근 6개월 매매가 평균: {last_avg_price}억원")

        # 최근 6개월 월세 평균
        last_avg_rent = int(df[-6:].mean()['월세'])
        print(f"- 최근 6개월 월세 평균: {last_avg_rent}만원")

        # 최근 월세 시세를 통해 추정한 기대 매매가
        s_val = df[-6:].mean()['월세'] * 12 * 30
        e_val = df[-6:].mean()['월세'] * 12 * 35
        print(f"- 최근 월세 시세를 통해 추정한 기대 매매가: :blue[{round(s_val/10000, 1)}억원] ~ :blue[{round(e_val/10000, 1)}억원]")

        # print(df3[-3:])
        print(df.iloc[-1]['PER'])
        last_PER = df.iloc[-1]['PER']

        # TODO: 해당 정보들을 별도 테이블로 만들어서 정기적으로 저장하자
        # sql = "SELECT * FROM APTLastPER WHERE apt_name = %s AND apt_PY = %s"
        # cur.execute(sql, (apt_name, apt_PY,))
        # # SELECT * FROM User WHERE createdAt BETWEEN DATE_ADD (NOW(), INTERVAL -1 DAY) AND NOW();
        # res = cur.fetchone()
        print(apt_name, apt_PY)
        response = supabase.table('APTLastPER').select('*').eq('apt_name', apt_name).eq('apt_PY', apt_PY).limit(
            1).execute()
        print(response)

        if response.data:
            res = response.data[0]
            # cur.execute(
            #     f"UPDATE APTLastPER SET "
            #     f"last_avg_price = '{last_avg_price}', last_avg_rent = '{last_avg_rent}', "
            #     f"last_PER = '{last_PER}' WHERE id = '{res['id']}'")
            # connection.commit()
            response = supabase.table('APTLastPER').update({
                'last_avg_price': last_avg_price,
                'last_avg_rent': last_avg_rent,
                'last_PER': last_PER,
                'updated': datetime.now().isoformat()
            }).eq('id', res['id']).execute()
        else:
            # print('최초 생성')
            # cur.execute(
            #     f"INSERT INTO APTLastPER (apt_name, apt_PY, last_avg_price, last_avg_rent, last_PER) "
            #     f"VALUES ('{apt_name}', '{apt_PY}', '{last_avg_price}', '{last_avg_rent}', '{last_PER}')")
            # connection.commit()
            response = supabase.table('APTLastPER').insert(
                {'apt_name': apt_name, 'apt_PY': apt_PY, 'last_avg_price': last_avg_price, 'last_avg_rent': last_avg_rent, 'last_PER': last_PER}).execute()


except Exception as e:
    print("Error:", e)

finally:
    print("Finished")
