import os
import time
from dataclasses import dataclass, field
import pandas as pd
import pandas_ta.momentum as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from binance.client import Client
from stock_ticker import StockTicker
import streamlit as st
from typing import Dict
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

@dataclass
class Values:
	ticker_csv: str
	selected_timeframe: str
	sma_windows: Dict[str, int] = field(default_factory=lambda: {'sma1_window': 20, 'sma2_window': 50, 'sma3_window': 100})

	def __post_init__(self):
		self.ticker_csv = self.ticker_csv.upper()
		self.selected_timeframe = self.selected_timeframe.lower()


class Supres(Values):
	@staticmethod
	def main_from_csv(ticker_csv, selected_timeframe='1d', candle_count=254):
		print(f"Start main function in {time.perf_counter() - perf} seconds\n"
			  f"{ticker_csv} data analysis in progress.")

		df = pd.read_csv(ticker_csv, delimiter=',', encoding="utf-8-sig", index_col=False, nrows=candle_count, keep_default_na=False)
		df = df.iloc[::-1]
		df['date'] = pd.to_datetime(df['date'], format="%Y-%m-%d")
		df = pd.concat([df, df.tail(1)], axis=0, ignore_index=True)
		df.dropna(inplace=True)

		Supres._main(ticker, df, selected_timeframe=selected_timeframe, candle_count=candle_count)

	@staticmethod
	def main(ticker, selected_timeframe='1d', candle_count=254, sma_windows={}):
		stockticker = StockTicker(database_url='duckdb:///main_supres/codes.ddb', read_only=True)
		normal_ticker = stockticker.normalize(ticker, yahoo=False)
		yahoo_ticker = stockticker.normalize(ticker, yahoo=True)
		if normal_ticker != yahoo_ticker:
			ticker = stockticker.get_name(normal_ticker)

		start = None
		limits = {'1m': 7, '2m': 60, '5m': 60, '15m': 60, '30m': 60, '60m': 730, '90m': 60, '1h': 730, '1d': None, '5d': None, '1wk': None, '1mo': None, '3mo': None,}
		limit = limits.get(selected_timeframe)
		# st.write(f"selected_timeframe: {selected_timeframe}")
		if limit is not None:
			start = datetime.today() - relativedelta(days=limit-1)
			# st.write(start)
		# df = yf.download(yahoo_ticker, start=start, interval=selected_timeframe)[-candle_count:]
		yfticker = yf.Ticker(yahoo_ticker)
		st.write(f"### {yfticker.info.get('shortName')}")
		df = yfticker.history(start=start, interval=selected_timeframe, period='max')[-candle_count:]

		if len(df) < candle_count:
			st.warning(f"**{ticker}** does not have enought candles to display ({len(df)})")
			st.write(df)
			return

		df.index.name = 'Date'
		df.reset_index(inplace=True)
		df.columns = [x.lower() for x in df.columns]
		df = pd.concat([df, df.tail(1)], axis=0, ignore_index=True)
		df.dropna(inplace=True)

		Supres._main(ticker, df, selected_timeframe=selected_timeframe, candle_count=candle_count)
		st.write(f"{yfticker.info['longBusinessSummary']}")

	@staticmethod
	def _main(ticker, df, selected_timeframe='1D', candle_count=254):
		if True:
			historical_hightimeframe = (Client.KLINE_INTERVAL_1DAY,
										Client.KLINE_INTERVAL_3DAY)
			historical_lowtimeframe = (Client.KLINE_INTERVAL_1MINUTE,
									   Client.KLINE_INTERVAL_3MINUTE,
									   Client.KLINE_INTERVAL_5MINUTE,
									   Client.KLINE_INTERVAL_15MINUTE,
									   Client.KLINE_INTERVAL_30MINUTE,
									   Client.KLINE_INTERVAL_1HOUR,
									   Client.KLINE_INTERVAL_2HOUR,
									   Client.KLINE_INTERVAL_4HOUR,
									   Client.KLINE_INTERVAL_6HOUR,
									   Client.KLINE_INTERVAL_8HOUR,
									   Client.KLINE_INTERVAL_12HOUR)
		else:
			historical_hightimeframe = ('1d', '3d')
			historical_lowtimeframe = ('1m', '3m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h')

		# Sma, Rsi, Macd, Fibonacci variables
		def indicators(sma1_window=20, sma2_window=50, sma3_window=100) -> tuple:  # [tuple, tuple, tuple, tuple]:
			"""
			Takes in three integer arguments, and returns a dataframe with three columns,
			each containing the moving average of the closing price for the given length.
			:param sma1_window: The length of the first moving average, defaults to 20 (optional)
			:param sma2_window: The length of the second moving average, defaults to 50 (optional)
			:param sma3_window: The length of the third moving average, defaults to 100 (optional)
			"""
			dfsma = df[:-1]
			sma_1 = tuple((dfsma.ta.sma(sma1_window)))
			sma_2 = tuple((dfsma.ta.sma(sma2_window)))
			sma_3 = tuple((dfsma.ta.sma(sma3_window)))
			rsi_tuple = tuple((ta.rsi(df['close'][:-1])))
			return {f'SMA{sma1_window}': sma_1, f'SMA{sma2_window}': sma_2, f'SMA{sma3_window}': sma_3, 'RSI': rsi_tuple}

		inds = indicators(**sma_windows)
		sma1, sma2, sma3, rsi = inds.values()

		support_list, resistance_list, fibonacci_uptrend, fibonacci_downtrend, pattern_list = [], [], [], [], []
		support_above, support_below, resistance_below, resistance_above, x_date = [], [], [], [], ''
		fibonacci_multipliers = 0.236, 0.382, 0.500, 0.618, 0.705, 0.786, 0.886
		# Chart settings
		legend_color, chart_color, background_color, support_line_color, resistance_line_color = \
			"#D8D8D8", "#E7E7E7", "#E7E7E7", "LightSeaGreen", "MediumPurple"
		fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
							vertical_spacing=0, row_width=[0.1, 0.1, 0.8])

		def support(candle_value, candle_index, before_candle_count, after_candle_count):  # -> (bool | None):
			"""
			If the price of the asset is increasing for the last before_candle_count and decreasing for
			the last after_candle_count, then return True. Otherwise, return False.
			"""
			try:
				for current_value in range(candle_index - before_candle_count + 1, candle_index + 1):
					if candle_value.low[current_value] > candle_value.low[current_value - 1]:
						return False
				for current_value in range(candle_index + 1, candle_index + after_candle_count + 1):
					if candle_value.low[current_value] < candle_value.low[current_value - 1]:
						return False
				return True
			except KeyError:
				pass

		def resistance(candle_value, candle_index, before_candle_count, after_candle_count):  # -> (bool | None):
			"""
			If the price of the stock is increasing for the last before_candle_count and decreasing for the last
			after_candle_count, then return True. Otherwise, return False.
			"""
			try:
				for current_value in range(candle_index - before_candle_count + 1, candle_index + 1):
					if candle_value.high[current_value] < candle_value.high[current_value - 1]:
						return False
				for current_value in range(candle_index + 1, candle_index + after_candle_count + 1):
					if candle_value.high[current_value] > candle_value.high[current_value - 1]:
						return False
				return True
			except KeyError:
				pass

		def fibonacci_pricelevels(high_price, low_price):  # -> tuple[list, list]:
			"""
			Uptrend Fibonacci Retracement Formula =>
			Fibonacci Price Level = High Price - (High Price - Low Price)*Fibonacci Level
			:param high_price: High price for the period
			:param low_price: Low price for the period
			"""
			for multiplier in fibonacci_multipliers:
				retracement_levels_uptrend = low_price + (high_price - low_price) * multiplier
				fibonacci_uptrend.append(retracement_levels_uptrend)
				retracement_levels_downtrend = high_price - (high_price - low_price) * multiplier
				fibonacci_downtrend.append(retracement_levels_downtrend)
			return fibonacci_uptrend, fibonacci_downtrend

		def candlestick_patterns() -> list:
			"""
			Takes in a dataframe and returns a list of candlestick patterns found in the dataframe then returns
			pattern list.
			"""
			from candlestick import candlestick
			nonlocal df
			df = candlestick.inverted_hammer(df, target='inverted_hammer')
			df = candlestick.hammer(df, target='hammer')
			df = candlestick.doji(df, target='doji')
			df = candlestick.bearish_harami(df, target='bearish_harami')
			df = candlestick.bearish_engulfing(df, target='bearish_engulfing')
			df = candlestick.bullish_harami(df, target='bullish_harami')
			df = candlestick.bullish_engulfing(df, target='bullish_engulfing')
			df = candlestick.dark_cloud_cover(df, target='dark_cloud_cover')
			df = candlestick.dragonfly_doji(df, target='dragonfly_doji')
			df = candlestick.hanging_man(df, target='hanging_man')
			df = candlestick.gravestone_doji(df, target='gravestone_doji')
			df = candlestick.morning_star(df, target='morning_star')
			df = candlestick.morning_star_doji(df, target='morning_star_doji')
			df = candlestick.piercing_pattern(df, target='piercing_pattern')
			df = candlestick.star(df, target='star')
			df = candlestick.shooting_star(df, target='shooting_star')
			df.replace({True: 'pattern_found'}, inplace=True)  # Dodge boolean 'True' output

			def pattern_find_func(pattern_row) -> list:
				"""
				The function takes in a dataframe and a list of column names. It then iterates through the
				list of column names and checks if the column name is in the dataframe. If it is, it adds
				the column name to a list and adds the date of the match to another list.
				"""
				t = 0
				pattern_find = [col for col in df.columns]
				for pattern in pattern_row:
					if pattern == 'pattern_found':
						# pattern, date
						pattern_list.append((pattern_find[t], pattern_row['date'].strftime('%b-%d-%y')))
					t += 1
				return pattern_list

			# Loop through the dataframe and find the pattern in the dataframe
			for item in range(-3, -30, -1):
				pattern_find_func(df.iloc[item])
			return pattern_list

		def sensitivity(sens=2):  # -> tuple[list, list]:
			"""
			Find the support and resistance levels for a given asset.
			sensitivity:1 is recommended for daily charts or high frequency trade scalping.
			:param sens: sensitivity parameter default:2, level of detail 1-2-3 can be given to function
			"""
			for sens_row in range(3, len(df) - 1):
				if support(df, sens_row, 3, sens):
					support_list.append((sens_row, df.low[sens_row]))
				if resistance(df, sens_row, 3, sens):
					resistance_list.append((sens_row, df.high[sens_row]))
			return support_list, resistance_list

		def chart_lines():
			"""
			Check if the support and resistance lines are above or below the latest close price.
			"""
			# Find support and resistance levels
			# Check if the support is below the latest close. If it is, it is appending it to the list
			# support_below. If it isn't, it is appending it to the list resistance_below.
			all_support_list = tuple(map(lambda sup1: sup1[1], support_list))
			all_resistance_list = tuple(map(lambda res1: res1[1], resistance_list))
			latest_close = df['close'].iloc[-1]
			for support_line in all_support_list:  # Find closes
				if support_line < latest_close:
					support_below.append(support_line)
				else:
					resistance_below.append(support_line)
			if len(support_below) == 0:
				support_below.append(df.low.min())
			# Check if the price is above the latest close price. If it is, it is appending it to the
			# resistance_above list. If it is not, it is appending it to the support_above list.
			for resistance_line in all_resistance_list:
				if resistance_line > latest_close:
					resistance_above.append(resistance_line)
				else:
					support_above.append(resistance_line)
			if len(resistance_above) == 0:
				resistance_above.append(df.high.max())
			return fibonacci_pricelevels(resistance_above[-1], support_below[-1])

		def legend_candle_patterns() -> None:
			"""
			The function takes the list of candlestick patterns and adds them to the chart as a legend text.
			"""
			fig.add_trace(go.Scatter(
				y=[support_list[0]], name="----------------------------------------", mode="markers",
				marker=dict(color=legend_color, size=14)))
			fig.add_trace(go.Scatter(
				y=[support_list[0]], name="Latest Candlestick Patterns", mode="markers",
				marker=dict(color=legend_color, size=14)))
			for pat1, count in enumerate(pattern_list):  # Candlestick patterns
				fig.add_trace(go.Scatter(
					y=[support_list[0]], name=f"{pattern_list[pat1][1]} : {str(pattern_list[pat1][0]).capitalize()}",
					mode="lines", marker=dict(color=legend_color, size=10)))

		def create_candlestick_plot() -> None:
			"""
			Creates a candlestick plot using the dataframe df, and adds it to the figure.
			"""
			fig.add_trace(go.Candlestick(x=df['date'][:-1].dt.strftime(x_date), name="Candlestick",
										 text=df['date'].dt.strftime(x_date), open=df['open'], high=df['high'],
										 low=df['low'], close=df['close']), row=1, col=1)


		def add_volume_subplot() -> None:
			"""
			Adds a volume subplot to the figure.
			"""
			fig.add_trace(go.Bar(x=df['date'][:-1].dt.strftime(x_date), y=df['volume'], name="volume",
								 showlegend=False), row=2, col=1)

		def add_rsi_subplot() -> None:
			"""
			Adds a subplot to the figure object called fig, which is a 3x1 grid of subplots. The
			subplot is a scatter plot of the RSI values, with a horizontal line at 30 and 70, and a gray
			rectangle between the two lines.
			"""
			fig.add_trace(go.Scatter(x=df['date'][:-1].dt.strftime(x_date), y=rsi, name="RSI",
									 showlegend=False), row=3, col=1)
			fig.add_hline(y=30, name="RSI lower band", line=dict(color='red', width=1), line_dash='dash', row=3, col=1)
			fig.add_hline(y=70, name="RSI higher band", line=dict(color='red', width=1), line_dash='dash', row=3, col=1)
			fig.add_hrect(y0=30, y1=70, line_width=0, fillcolor="gray", opacity=0.2, row=3, col=1)

		def draw_support() -> None:
			"""
			Draws the support lines and adds annotations to the chart.
			"""
			c = 0
			while True:
				if c > len(support_list) - 1:
					break
				# Support lines
				fig.add_shape(type='line', x0=support_list[c][0] - 1, y0=support_list[c][1],
							  x1=len(df) + 25,
							  y1=support_list[c][1], line=dict(color=support_line_color, width=2))
				# Support annotations
				fig.add_annotation(x=len(df) + 7, y=support_list[c][1], text=str(support_list[c][1]),
								   font=dict(size=15, color=support_line_color))
				c += 1

		def draw_resistance() -> None:
			"""
			Draws the resistance lines and adds annotations to the chart.
			"""
			c = 0
			while True:
				if c > len(resistance_list) - 1:
					break
				# Resistance lines
				fig.add_shape(type='line', x0=resistance_list[c][0] - 1, y0=resistance_list[c][1],
							  x1=len(df) + 25,
							  y1=resistance_list[c][1], line=dict(color=resistance_line_color, width=1))
				# Resistance annotations
				fig.add_annotation(x=len(df) + 20, y=resistance_list[c][1], text=str(resistance_list[c][1]),
								   font=dict(size=15, color=resistance_line_color))
				c += 1

		def legend_texts() -> None:
			"""
			Adds a trace to the chart for each indicator, and then adds a trace for each indicator's value.
			"""
			fig.add_trace(go.Scatter(
				y=[support_list[0]], name=f"Resistances    ||   Supports", mode="markers+lines",
				marker=dict(color=resistance_line_color, size=10)))
			str_price_len = 3
			sample_price = df['close'][0]
			if sample_price < 1:
				str_price_len = len(str(sample_price))

			def legend_support_resistance_values() -> None:
				"""
				Takes the support and resistance values and adds them to the legend.
				"""
				temp = 0
				blank = " " * (len(str(sample_price)) + 1)
				differ = abs(len(float_resistance_above) - len(float_support_below))
				try:
					if differ < 0:
						for i in range(differ):
							float_resistance_above.extend([0])
					if differ >= 0:
						for i in range(differ):
							float_support_below.extend([0])
					for _ in range(max(len(float_resistance_above), len(float_support_below))):
						if float_resistance_above[temp] == 0:  # This is for legend alignment
							legend_supres = f"{float(float_resistance_above[temp]):.{str_price_len - 1}f}{blank}     " \
											f"||   {float(float_support_below[temp]):.{str_price_len - 1}f}"
						else:
							legend_supres = f"{float(float_resistance_above[temp]):.{str_price_len - 1}f}       " \
											f"||   {float(float_support_below[temp]):.{str_price_len - 1}f}"
						fig.add_trace(go.Scatter(y=[support_list[0]], name=legend_supres, mode="lines",
									  marker=dict(color=legend_color, size=10)))
						if temp <= 14:
							temp += 1
						else:
							break
				except IndexError:
					pass

			def text_and_indicators() -> None:
				"""
				Adds a trace to the chart for each indicator, and then adds a trace for each indicator's value.
				"""
				# fig.add_trace(go.Scatter(
				#     y=[support_list[0]], name=f"github.com/arabacibahadir/sup-res", mode="markers",
				#     marker=dict(color=legend_color, size=0)))
				# fig.add_trace(go.Scatter(
				#     y=[support_list[0]], name=f"-------  twitter.com/wykonos  --------", mode="markers",
				#     marker=dict(color=legend_color, size=0)))
				fig.add_trace(go.Scatter(
					y=[support_list[0]], name=f"Indicators", mode="markers", marker=dict(color=legend_color, size=14)))
				fig.add_trace(go.Scatter(
					y=[support_list[0]], name=f"RSI        : {int(rsi[-1])}", mode="lines",
					marker=dict(color=legend_color, size=10)))
				# Add SMA10, SMA50, and SMA100 to the chart and legend
				sma1_name, sma2_name, sma3_name, _ = inds.keys()
				fig.add_trace(go.Scatter(x=df['date'].dt.strftime(x_date), y=sma1,
										 name=f"{sma1_name}     : {float(sma1[-1]):.{str_price_len}f}",
										 line=dict(color='#5c6cff', width=3)))
				fig.add_trace(go.Scatter(x=df['date'].dt.strftime(x_date), y=sma2,
										 name=f"{sma2_name}     : {float(sma2[-1]):.{str_price_len}f}",
										 line=dict(color='#950fba', width=3)))
				fig.add_trace(go.Scatter(x=df['date'].dt.strftime(x_date), y=sma3,
										 name=f"{sma3_name}     : {float(sma3[-1]):.{str_price_len}f}",
										 line=dict(color='#a69b05', width=3)))
				fig.add_trace(go.Scatter(
					y=[support_list[0]], name=f"-- Fibonacci Uptrend | Downtrend --", mode="markers",
					marker=dict(color=legend_color, size=0)))

			def legend_fibonacci() -> None:
				"""
				Adds to the legend for each Fibonacci level text.
				"""
				mtp = len(fibonacci_multipliers) - 1
				for _ in fibonacci_uptrend:
					fig.add_trace(go.Scatter(
						y=[support_list[0]],
						name=f"Fib {fibonacci_multipliers[mtp]:.3f} "
							 f": {float(fibonacci_uptrend[mtp]):.{str_price_len}f} "
							 f"| {float(fibonacci_downtrend[mtp]):.{str_price_len}f} ",
						mode="lines",
						marker=dict(color=legend_color, size=10)))
					mtp -= 1

			legend_support_resistance_values()
			text_and_indicators()
			legend_fibonacci()
			# Candle patterns for HTF
			# if selected_timeframe in historical_hightimeframe:
			if not selected_timeframe[-1] in ('h', 'm'):
				legend_candle_patterns()

		def chart_updates() -> None:
			"""
			Updates the chart's layout, background color, chart color, legend color, and margin.
			"""
			fig.update_layout(title=str(f"{ticker} {selected_timeframe.upper()} Chart"),
							  hovermode='x', dragmode="zoom",
							  paper_bgcolor=background_color, plot_bgcolor=chart_color, xaxis_rangeslider_visible=False,
							  legend=dict(bgcolor=legend_color, font=dict(size=11)), margin=dict(t=30, l=0, b=0, r=0))
			fig.update_xaxes(showspikes=True, spikecolor="green", spikethickness=2)
			fig.update_yaxes(showspikes=True, spikecolor="green", spikethickness=2)

		def save():
			"""
			Saves the image and html file of the plotly chart, then it tweets the image and text
			"""
			if not os.path.exists("../main_supres/images"):
				os.mkdir("images")
			image = \
				f"../main_supres/images/{df['date'].dt.strftime('%b-%d-%y')[candle_count]}{ticker}.jpeg"
			fig.write_image(image, width=1920, height=1080)  # Save image for tweet
			fig.write_html(
				f"../main_supres/images/"
				f"{df['date'].dt.strftime('%b-%d-%y')[candle_count]}{ticker}.html",
				full_html=False, include_plotlyjs='cdn')
			text_image = f"#{ticker} #{historical_data.symbol_data.get('baseAsset')} " \
						 f"{selected_timeframe} Support and resistance levels \n " \
						 f"{df['date'].dt.strftime('%b-%d-%Y')[candle_count]} #crypto #btc"

			def send_tweet() -> None:
				"""
				Takes a screenshot of a chart, then tweets it with a caption.
				"""
				import tweet
				tweet.send_tweet(image, text_image)
				while tweet.is_image_tweet().text != text_image:
					time.sleep(1)
					if tweet.is_image_tweet().text != text_image:
						resistance_above_nonzero = list(filter(lambda x: x != 0, float_resistance_above))
						support_below_nonzero = list(filter(lambda x: x != 0, float_support_below))
						tweet.api.update_status(status=f"#{ticker}  "
													   f"{df['date'].dt.strftime('%b-%d-%Y')[candle_count]} "
													   f"{selected_timeframe} Support and resistance levels"
													   f"\nRes={resistance_above_nonzero[:7]} \n"
													   f"Sup={support_below_nonzero[:7]}",
												in_reply_to_status_id=tweet.is_image_tweet().id)
					break
			# send_tweet()

		def pinescript_code() -> str:
			"""
			It takes resistance and support lines, and writes them to a file called pinescript.txt.
			"""
			pinescript_lines = []
			lines_sma = f"//@version=5\nindicator('Sup-Res {ticker} {selected_timeframe}'," \
						f" overlay=true)\n" \
						"plot(ta.sma(close, 50), title='50 SMA', color=color.new(color.blue, 0), linewidth=1)\n" \
						"plot(ta.sma(close, 100), title='100 SMA', color=color.new(color.purple, 0), linewidth=1)\n" \
						"plot(ta.sma(close, 200), title='200 SMA', color=color.new(color.red, 0), linewidth=1)\n"

			for line_res in float_resistance_above[:10]:
				if line_res == 0:
					continue
				lr = f"hline({line_res}, title=\"Lines\", color=color.red, linestyle=hline.style_solid, linewidth=1)"
				pinescript_lines.append(lr)

			for line_sup in float_support_below[:10]:
				if line_sup == 0:
					continue
				ls = f"hline({line_sup}, title=\"Lines\", color=color.green, linestyle=hline.style_solid, linewidth=1)"
				pinescript_lines.append(ls)
			lines = '\n'.join(map(str, pinescript_lines))
			# Create a new file that called pinescript.txt and write the lines_sma and lines variables to the file
			with open("../main_supres/pinescript.txt", "w") as pine:
				pine.writelines(lines_sma + lines)
			return lines

		sensitivity()
		chart_lines()
		# Checking if the selected timeframe is in the historical_hightimeframe list.
		if selected_timeframe in historical_hightimeframe:
			candlestick_patterns()
			x_date = '%b-%d-%y'
		elif selected_timeframe in historical_lowtimeframe:
			x_date = '%H:%M %d-%b'
		create_candlestick_plot()
		add_volume_subplot()
		add_rsi_subplot()
		float_resistance_above = list(map(float, sorted(resistance_above + resistance_below)))
		float_support_below = list(map(float, sorted(support_below + support_above, reverse=True)))
		draw_support()
		draw_resistance()
		legend_texts()
		chart_updates()
		# save()
		# pinescript_code()
		# print(df)
		print(f"Completed execution in {time.perf_counter() - perf} seconds")
		# return fig.show(id='the_graph', config={'displaylogo': False})
		fig.update_layout(height=800)
		st.plotly_chart(fig, use_container_width=True)


def action(ticker, selected_timeframe='1d', sma_windows={}, candle_count=254):
	if False:
		import historical_data

		os.chdir("../main_supres")  # Change the directory to the main_supres folder
		file_name = historical_data.file_name
		ticker = historical_data.ticker
		try:
			perf = time.perf_counter()
			historical_data.historical_data_write(ticker)
			if os.path.isfile(file_name):  # Check .csv file is there or not
				print(f"{file_name} downloaded and created.")
				Supres.main_from_csv(file_name, historical_data.time_frame)
				print("Data analysis is done. Browser opening.")
				# remove the .csv file
				os.remove(file_name)
				print(f"{file_name} file deleted.")
			else:
				raise print("One or more issues caused the download to fail. "
							"Make sure you typed the filename correctly.")

		except KeyError:
			os.remove(file_name)
			raise KeyError("Key error, algorithm issue")

	else:
		perf = time.perf_counter()
		Supres.main(ticker, selected_timeframe=selected_timeframe, sma_windows=sma_windows, candle_count=candle_count)


@st.cache
def get_listing(market: str) -> pd.DataFrame:
	s = StockTicker(database_url='duckdb:///main_supres/codes.ddb', read_only=True)
	df = s.get_listing(market)
	df = df.dropna()
	return df

if __name__ == "__main__":
	st.set_page_config(layout="wide")

	perf = time.perf_counter()
	# fire.Fire(action)

	ticker = None
	with st.sidebar:
		st.write("## Ticker Settings")
		kind = st.radio('Select search type', ['by Name', 'by Ticker', 'from List'], index=2)
		ticker = None
		if kind == 'by Name':
			ticker = st.text_input('Stock Name:', '')
		elif kind == 'by Ticker':
			ticker = st.text_input('Stock Ticker:', '')
		elif kind == 'from List':
			market = st.selectbox('Select market', ['KRX', 'KOSPI', 'KOSDAQ', 'US', 'NYSE', 'NASDAQ', 'AMEX'], index=0)
			df = get_listing(market)
			ii = df.index[df['name'] == '????????????']
			if len(ii) > 0:
				index = int(ii[0])
			else:
				index = 0

			code_name = st.selectbox('Stock Ticker:', df.code + ' (' + df.name + ')', index=index)
			ticker = code_name.split(' ')[0]

		st.write("## Data Fetch Setting")
		selected_timeframe = st.selectbox('Timeframe', ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'], index=8)
		candle_count = st.number_input('Number of candles', min_value=100, value=254)

		st.write("## SMA Window Settings")
		ma_length1 = st.number_input('SMA1 Window', min_value=5, value=20)
		ma_length2 = st.number_input('SMA2 Window', min_value=5, value=50)
		ma_length3 = st.number_input('SMA3 Window', min_value=5, value=100)
		sma_windows = {'sma1_window': ma_length1, 'sma2_window': ma_length2, 'sma3_window': ma_length3}

	if kind == 'from List' or st.sidebar.button('Go'):
		action(ticker, selected_timeframe=selected_timeframe, sma_windows=sma_windows, candle_count=candle_count)