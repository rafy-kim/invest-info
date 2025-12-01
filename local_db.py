"""
로컬 PostgreSQL 데이터베이스 연결 모듈
"""
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# 로컬 PostgreSQL 연결 설정
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://localhost/invest_info"
)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class LocalSupabaseClient:
    """
    Supabase 클라이언트와 유사한 인터페이스를 제공하는 로컬 DB 클라이언트
    """
    def table(self, table_name):
        return TableQuery(table_name)


class TableQuery:
    def __init__(self, table_name):
        self.table_name = table_name
        self._select_cols = "*"
        self._conditions = []
        self._limit_val = None
        self._single = False

    def select(self, cols, count=None):
        self._select_cols = cols
        # count 매개변수는 Supabase 호환을 위해 받지만 로컬에서는 무시
        return self

    def eq(self, col, val):
        self._conditions.append((col, val))
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def single(self):
        self._single = True
        self._limit_val = 1
        return self

    def _quote_column(self, col):
        """대소문자 구분이 필요한 컬럼명을 쌍따옴표로 감싸기"""
        case_sensitive_cols = ["PY", "DEAL_TYPE", "last_PER", "apt_PY"]
        col = col.strip()
        if col in case_sensitive_cols:
            return f'"{col}"'
        return col

    def _process_select_cols(self, cols):
        """SELECT 절의 컬럼명들을 처리"""
        if cols == "*":
            return cols
        # 콤마로 분리하고 각 컬럼 처리
        col_list = [c.strip() for c in cols.split(',')]
        return ', '.join(self._quote_column(c) for c in col_list)

    def execute(self):
        session = Session()
        try:
            # SQL 쿼리 생성
            cols = self._process_select_cols(self._select_cols)
            sql = f'SELECT {cols} FROM "{self.table_name}"'

            params = {}
            if self._conditions:
                where_clauses = []
                for i, (col, val) in enumerate(self._conditions):
                    param_name = f"param_{i}"
                    # 대소문자 구분되는 컬럼명 처리
                    if col in ["PY", "DEAL_TYPE", "last_PER", "apt_PY"]:
                        where_clauses.append(f'"{col}" = :{param_name}')
                    else:
                        where_clauses.append(f"{col} = :{param_name}")
                    params[param_name] = val
                sql += " WHERE " + " AND ".join(where_clauses)

            if self._limit_val:
                sql += f" LIMIT {self._limit_val}"

            result = session.execute(text(sql), params)
            rows = result.fetchall()
            columns = result.keys()

            data = [dict(zip(columns, row)) for row in rows]

            if self._single:
                return QueryResult(data[0] if data else None)
            return QueryResult(data)
        finally:
            session.close()

    def update(self, values):
        return UpdateQuery(self.table_name, values, self._conditions)

    def insert(self, values):
        return InsertQuery(self.table_name, values)


class InsertQuery:
    def __init__(self, table_name, values):
        self.table_name = table_name
        self.values = values

    def execute(self):
        session = Session()
        try:
            cols = []
            placeholders = []
            params = {}

            for i, (col, val) in enumerate(self.values.items()):
                param_name = f"val_{i}"
                if col in ["PY", "DEAL_TYPE", "last_PER", "apt_PY"]:
                    cols.append(f'"{col}"')
                else:
                    cols.append(col)
                placeholders.append(f":{param_name}")
                params[param_name] = val

            sql = f'INSERT INTO "{self.table_name}" ({", ".join(cols)}) VALUES ({", ".join(placeholders)})'

            session.execute(text(sql), params)
            session.commit()
            return QueryResult(None)
        finally:
            session.close()


class UpdateQuery:
    def __init__(self, table_name, values, conditions=None):
        self.table_name = table_name
        self.values = values
        self._conditions = conditions or []

    def eq(self, col, val):
        self._conditions.append((col, val))
        return self

    def execute(self):
        session = Session()
        try:
            set_clauses = []
            params = {}

            for i, (col, val) in enumerate(self.values.items()):
                param_name = f"set_{i}"
                if col in ["PY", "DEAL_TYPE", "last_PER", "apt_PY"]:
                    set_clauses.append(f'"{col}" = :{param_name}')
                else:
                    set_clauses.append(f"{col} = :{param_name}")
                params[param_name] = val

            sql = f'UPDATE "{self.table_name}" SET ' + ", ".join(set_clauses)

            if self._conditions:
                where_clauses = []
                for i, (col, val) in enumerate(self._conditions):
                    param_name = f"where_{i}"
                    if col in ["PY", "DEAL_TYPE", "last_PER", "apt_PY"]:
                        where_clauses.append(f'"{col}" = :{param_name}')
                    else:
                        where_clauses.append(f"{col} = :{param_name}")
                    params[param_name] = val
                sql += " WHERE " + " AND ".join(where_clauses)

            session.execute(text(sql), params)
            session.commit()
            return QueryResult(None)
        finally:
            session.close()


class QueryResult:
    def __init__(self, data):
        self.data = data


# 전역 클라이언트 인스턴스
supabase = LocalSupabaseClient()
