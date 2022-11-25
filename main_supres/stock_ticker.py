from sqlalchemy import create_engine
from sqlalchemy.engine import ddl
import duckdb
from dataclasses import dataclass
from sqlalchemy.engine.base import Engine
import pandas as pd

@dataclass
class StockTicker:
	database_url: str = "sqlite:///codes.sqlite"
	engine: Engine = None
	read_only:bool = False

	def __post_init__(self):
		connect_args={}
		if self.read_only:
			connect_args = {'read_only': True}
		self.engine = create_engine(self.database_url, connect_args=connect_args)

	def execute(self, statement, *multiparams, **params):
		if self.database_url.startswith('duckdb:') and len(multiparams) > 0:
			for name, _ in multiparams[0].items():
				statement = statement.replace(f':{name}', '?')
			# print(f"=== statement: {statement}")
			return self.engine.execute(statement, list(multiparams[0].values()))
		else:
			return self.engine.execute(statement, *multiparams, **params)

	def is_krx_code(self, ticker):
		if len(ticker) == 6 and ticker[:-1].isdigit():  # KRX 종목코드
			return True
		return False

	def get_ticker(self, name: str, market=None, yahoo=False) -> str:
		params = {'name': name.upper()}
		op = '='
		if '_' in name or '%' in name:
			op = 'LIKE'

		sql = f"SELECT code, name, market FROM tickers WHERE name {op} :name"
		if market is not None:
			sql += f" AND market=:market"
			params['market'] = market

		res = self.execute(sql, params)
		rows = res.fetchall()

		if len(rows) > 0:
			code, name, market = rows[0]
			if market in ('kospi', 'kosdaq'):
				ret = code[1:]
				if yahoo:
					ret = ret + '.KS' if market == 'kospi' else ret + '.KQ' if market == 'kosdaq' else ret
			else:
				ret = code
			return ret
		return None

	get_code = get_ticker

	def get_market(self, ticker):
		if self.is_krx_code(ticker):
			ticker = 'A' + ticker

		params = {'code': ticker.upper()}
		op = '='
		if '_' in ticker or '%' in ticker:
			op = 'LIKE'

		sql = f"SELECT code, market FROM tickers WHERE code {op} :code"
		res = self.execute(sql, params)
		rows = res.fetchall()

		if len(rows) > 0:
			code, market = rows[0]
			return market
		return None

	def normalize(self, ticker_or_name, market=None, yahoo=False):
		if self.is_krx_code(ticker_or_name):
			if yahoo:
				market = self.get_market(ticker_or_name)
				if market == 'kospi':
					return ticker_or_name + '.KS'
				elif market == 'kosdaq':
					return ticker_or_name + '.KQ'
			else:
				return ticker_or_name
		else:
			res = self.get_name(ticker_or_name, market=market)
			if res is not None:
				return ticker_or_name
			res = self.get_code(ticker_or_name, market=market, yahoo=yahoo)
			if res is not None:
				return res
			return ticker_or_name
	
	def get_name(self, ticker: str, market=None) -> str:
		if len(ticker) == 6 and ticker[:-1].isdigit():  # KRX 종목코드
			ticker = 'A' + ticker

		params = {'code': ticker.upper()}
		op = '='
		if '_' in ticker or '%' in ticker:
			op = 'LIKE'

		sql = f"SELECT code, name FROM tickers WHERE code {op} :code"
		if market is not None:
			sql += f" AND market=:market"
			params['market'] = market
		# print(sql, params)
		res = self.execute(sql, params)
		rows = res.fetchall()
		if len(rows) > 0:
			return rows[0][1]
		return None

	def get_listing(self, market: str) -> list:
		market = market.lower()
		where = []
		params = {}
		sql = "SELECT code, name, market FROM tickers"

		if market == 'all':
			pass
		elif market == 'krx':
			where.append("market=:market1 or market=:market2")
			params['market1'] = 'kospi'
			params['market2'] = 'kosdaq'
		elif market == 'us':
			where.append("market=:market1 or market=:market2 or market=:market3")
			params['market1'] = 'nyse'
			params['market2'] = 'nasdaq'
			params['market3'] = 'amex'
		elif market in ['kospi', 'kosdaq', 'nyse', 'nasdaq', 'amex']:
			where.append("market=:market")
			params['market'] = market
		else:
			raise ValueError(f"'{market}' is an invalid market name")

		if len(where) > 0:
			sql = sql + f" WHERE {' OR '.join(where)}"

		res = self.execute(sql, params)
		df = pd.DataFrame(res.fetchall(), columns=res.keys())

		def fix_krx_code(row):
			# print("--", row)
			if row['market'] in ['kospi', 'kosdaq']:
				row['code'] = row['code'][1:]
			return row

		# df['code']. = [x[1:] for x in df['code'].values]
		df = df.apply(fix_krx_code, axis=1)

		return df