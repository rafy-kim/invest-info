import json
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
import os
import MySQLdb
from MySQLdb.cursors import DictCursor
from supabase import create_client, Client

from apt_value import get_APT_transactions, get_APT_info

# Load environment variables from the .env file
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


try:
    # Create a cursor to interact with the database
    response = supabase.table('APTInfo').select('name, PY, r_id, description', count='exact').eq('status', 1).execute()
    for r in response.data[:5]:
        ####
        apt_name = r['name']
        PY = r['PY']
        print(f"{apt_name} - {PY}")

        apt_info = {
            'desc': r['description'],
            'r_id': r['r_id'],
            'name': r['name'],
        }

        # TODO: 주력 평형 정보 업데이트

        url = f"https://api-m.richgo.ai/api/data/danji/onepage?danjiId={r['r_id']}"
        headers = {
            'Referer': 'https://m.richgo.ai',
            'Content-Type': 'application/json; charset=utf-8'  # 추가된 부분: JSON 형식임을 명시
        }
        r = requests.get(url, headers=headers)

        if r.status_code != 200:  # 상태 코드가 200일 때만 JSON을 파싱
            print(f"Error: {r.status_code}")
            break

        data = r.json()['result']['pyeongList']
        for d in data:
            print(d['pyeongType'])
            print(d['households'])

        break





        # 1은 매매, 2는 전세, 3은 월세
        deal_types = range(1, 4)
        for d in deal_types:
            DEAL_TYPE = str(d)

            # sql = "SELECT * FROM APTInfo WHERE name = %s AND PY = %s AND DEAL_TYPE = %s"
            # cur.execute(sql, (apt_name, PY, DEAL_TYPE,))
            # res = cur.fetchone()
            response = supabase.table('APTInfo').select('*', count='exact').eq('name', apt_name).eq('PY', PY).eq('DEAL_TYPE', DEAL_TYPE).execute()
            res = response.data[0]
            if not res:
                print(f'{apt_name} - {PY} - {DEAL_TYPE}: 데이터 없음')

            price_trend = json.loads(res['price_trend'])
            print("현재 price_trend:")
            print(price_trend)

            # 오늘 날짜
            today = datetime.today()
            # TODO: 오늘 날짜를 고려해서 최근 6개월치만 업데이트하기
            # 3개월 전 날짜
            prev_date = today - timedelta(days=180)
            str_date = prev_date.strftime("%Y%m")
            print(f'기준일: {str_date}')
            price_trend = [d for d in price_trend if d['date'] < str_date]
            print(price_trend)

            years = range(prev_date.year, today.year + 1)
            for y in years:
                YEAR = str(y)
                print(f'{YEAR}로 가져 온 아실 데이터')
                amount = get_APT_transactions(apt_info, PY, YEAR, DEAL_TYPE)
                amount = sorted(amount, key=lambda x: x['date'])
                print(amount)

                print(f'{YEAR}로 가져 온 아실 데이터 중 이어 붙일 데이터')
                filtered_amount = [d for d in amount if d['date'] >= str_date]
                print(filtered_amount)
                price_trend.extend(filtered_amount)

            print("최종적으로 DB에 업데이트 할 price_trend 데이터")
            print(price_trend)

            # cur.execute(
            #     f"UPDATE APTInfo SET price_trend  = '{json.dumps(price_trend)}' WHERE id = '{res['id']}'")
            # connection.commit()

            # TODO: 주석 해제 필요
            # response = supabase.table('APTInfo').update({'price_trend': json.dumps(price_trend)}).eq('id', res['id']).execute()
            # print("업데이트 완료!!")



except MySQLdb.Error as e:
    print("MySQL Error:", e)

finally:
    # Close the cursor and connection
    # cur.close()
    # connection.close()

    print('Finished')
