import csv
import pandas as pd
from binance.client import Client
import frameselect

print("Ticker and Time Frame:")  # Example:"BTCUSDT 1H", "ETHBTC 3D", "BNBUSDT 15M"
if False:
    ticker, frame_s = str(input().upper()).split()
else:
    ticker, frame_s = 'BTCUSDT 1D'.split()

time_frame = frameselect.frame_select(frame_s)[0]
start = frameselect.frame_select(frame_s)[1]
is_binance_ticker = True
# Creating a client object that is used to interact with the Binance API
client = Client("", "")
if any(ticker == i.get('symbol') for i in client.get_all_tickers()):  # Check pair is in Binance API
    print("Pair is in Binance API.")
else:
    print("Pair is not in Binance API.")
    # exit()
    is_binance_ticker = True

file_name = ticker + ".csv"
symbol_data = client.get_symbol_info(ticker)
header_list = ('unix', 'open', 'high', 'low', 'close', 'volume', 'close time', 'volume', 'tradecount',
               'taker buy vol', 'taker buy quote vol', 'ignore')


def historical_data_write(ticker_symbol):
    """
    Write the historical data to a csv file
    """
    csv_file_w = open(file_name, "w", newline='')
    klines_writer = csv.writer(csv_file_w, delimiter=",")
    klines_writer.writerow(header_list)
    for candlestick in reversed(client.get_historical_klines(symbol=ticker_symbol, interval=time_frame,
                                                             start_str=start, limit=300)):
        klines_writer.writerow(candlestick)
    csv_file_w.close()
    df = pd.read_csv(file_name)
    # Converting the unix time to a readable date format for today
    date = pd.to_datetime(df['unix'], unit='ms')
    df.insert(1, 'date', date)
    df.drop(labels=["unix", "volume.1", "close time", "tradecount", "taker buy vol", "taker buy quote vol", "ignore"], inplace=True, axis=1)
    df.to_csv(file_name, index=False)
    print("Data writing:", file_name)
