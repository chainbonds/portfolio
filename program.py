import requests
from binance.client import Client
import time
import numpy as np
import math
import pandas as pd
from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns
import json
import subprocess

def opt_weights(df_assets_opt):
	mu = expected_returns.mean_historical_return(df_assets_opt)	
	S = risk_models.sample_cov(df_assets_opt)
	ef = EfficientFrontier(mu, S, weight_bounds=(0, 1))
	try:
		weights = ef.efficient_return(0.0, market_neutral=False)
		weights = ef.clean_weights()
		ret_tangent, std_tangent, sharpe = ef.portfolio_performance(risk_free_rate=0.0, verbose=True)
		return [ sharpe, np.array( list( weights.items() ) )[:,1].astype(float) ]
	except:
		return [ 0.0, np.zeros( len(df_assets_opt.columns) ) ]

def send_message( names, weights ):
	files = 'weight_status.json'
	message = [{'lp': n, 'weight': w} for n, w in zip(names, weights)]
	with open(files, 'w') as jsonfile:
		json.dump(message, jsonfile)
	
def compute_weights(no_pairs):
	one_day_milli = int( 86400000 )
	now_milli = int(round(time.time() * 1000))
	one_quarter_milli = int( 31556952000 )
	seven_days = int( 7 * one_day_milli )

	r = requests.get('https://api.atrix.finance/api/pools').json()
	atrix_json = []
	for pool in r['pools']:
#		print( pool['market'] )
		try:
			r2 = requests.get('https://api.solscan.io/amm/tvl?address=' + pool['market'] + '&type=1D&time_from=' + str( (now_milli - seven_days) / 1000.0 ) + '&time_to=' + str( (now_milli) / 1000.0 ) ).json()
		except:
			continue
		last_tvl = 0
		counter = 0
		for item2 in r2['data']['items']:
			last_tvl = last_tvl + item2['value']
			counter = counter + 1
		if counter > 0:	
			last_tvl = last_tvl / counter	

		try:
			r2 = requests.get('https://api.solscan.io/amm/ohlcv?address=' + pool['market'] + '&type=1D&time_from=' + str( (now_milli - seven_days) / 1000.0 ) + '&time_to=' + str( (now_milli) / 1000.0 ) ).json()
		except:
			continue
#		print('https://api.solscan.io/amm/ohlcv?address=' + pool['market'] + '&type=1D&time_from=' + str( (now_milli - seven_days) / 1000.0 ) + '&time_to=' + str( (now_milli) / 1000.0 ))
#		print('https://api.solscan.io/amm/tvl?address=' + pool['market'] + '&type=1D&time_from=' + str( (now_milli - seven_days) / 1000.0 ) + '&time_to=' + str( (now_milli) / 1000.0 ) )
		last_vol = 0
		counter = 0
		symbol = ''
		for item2 in r2['data']['items']:
			last_vol = last_vol + item2['v']
			counter = counter + 1
			symbol = item2['symbol']
		if counter > 0:
			last_vol = last_vol / counter

		if last_tvl > 0.0 and last_vol < last_tvl:
			apy = 0.2 * last_vol / last_tvl
		else:
			apy = 0.0

		print(apy)

		apy = ( math.pow( 1.0 + ( apy / 100.0 ), 365.25 ) - 1.0 ) * 100.0
		print( symbol, last_tvl, last_vol, apy )

		if symbol!="":
			x = '{ "name": "", "apy": 0, "liquidity": 0, "volume_7d": 0, "official": ""}'
			y = json.loads(x)
			y['name'] = symbol
			y['apy'] = apy
			y['liquidity'] = last_tvl
			y['volume_7d'] = last_vol
			y['official'] = True

			atrix_json.append(y) 
		
	client = Client()
	response = client.get_exchange_info()

	binance_assets = []
	binance_symbols = []
	for item in response['symbols']:
		if ( item['baseAsset'] == 'USDT' or item['quoteAsset'] == 'USDT' ) and ( len(item['baseAsset']) > 2 and len(item['quoteAsset']) ):
			binance_assets.append( item['baseAsset'] )	
			binance_assets.append( item['quoteAsset'] )	
			binance_symbols.append( item['symbol'] )		

	binance_assets = list(set(binance_assets))
	#print( binance_assets )
	exceptions = ['MEDIA', 'ISOLA', 'SOLC'] #excluded from the analysis

#	r = requests.get('https://api.raydium.io/pairs').json()
	r = atrix_json

	names = []
	apy = []
	liquidity = []
	ray_assets = []
	equiv_assets = []
	volume7d = []
	for item in r:
		if item['official']==True:
			base = item['name'].split("-")[0]
			quote = item['name'].split("-")[1]
	
			both_assets_ray = []
			both_assets_binance = []
			for asset in binance_assets:
				if not(base in exceptions or quote in exceptions):
					if asset in base:								
						both_assets_ray.append( base )				
						both_assets_binance.append( asset )				
					if asset in quote:								
						both_assets_ray.append( quote )	
						both_assets_binance.append( asset )				
				else:
					if asset==base:								
						both_assets_ray.append( base )				
						both_assets_binance.append( asset )				
					if asset==quote:								
						both_assets_ray.append( quote )	
						both_assets_binance.append( asset )				

			if len(both_assets_ray) == 2:
				names.append(item['name'])
				apy.append(item['apy'])
				liquidity.append(item['liquidity'])
				volume7d.append(item['volume_7d'])
				equiv_assets.append( both_assets_binance )		
	
#				print( item['name'], both_assets_binance )


	zipped = zip(apy, volume7d, liquidity, names, equiv_assets)
	zipped = sorted(zipped, reverse=True)

	apy, volume7d, liquidity, names, equiv_assets = list(zip(*zipped))

	#print(names)
	#print(equiv_assets)
	#print(apy)
	full_names = []
	full_prices = []
	for it in range(len(names))[:no_pairs]:
		apd = math.pow( 1.0 + ( apy[it] / 100.0 ), 1.0 / 365.25 ) - 1.0
		synthetic_price = []
		price1 = []
		if equiv_assets[it][0]!='USDT':
			pair = equiv_assets[it][0] + 'USDT' 
			if pair in binance_symbols:
				klines = client.get_historical_klines(pair, Client.KLINE_INTERVAL_1DAY, now_milli - one_quarter_milli, now_milli )	
				for j in range(len(klines)):
					price1.append( float(klines[j][4])/float(klines[0][4]) )	
			else:
				pair = 'USDT' + equiv_assets[it][0] 
				klines = client.get_historical_klines(pair, Client.KLINE_INTERVAL_1DAY, now_milli - one_quarter_milli, now_milli )	
				for j in range(len(klines)):
					price1.append( float(klines[0][4])/float(klines[j][4]) )	
	
		price2 = []
		if equiv_assets[it][1]!='USDT':
			pair = equiv_assets[it][1] + 'USDT' 
			if pair in binance_symbols:
				klines = client.get_historical_klines(pair, Client.KLINE_INTERVAL_1DAY, now_milli - one_quarter_milli, now_milli )	
				for j in range(len(klines)):
					price2.append( float(klines[j][4])/float(klines[0][4]) )	
			else:
				pair = 'USDT' + equiv_assets[it][0] 
				klines = client.get_historical_klines(pair, Client.KLINE_INTERVAL_1DAY, now_milli - one_quarter_milli, now_milli )	
				for j in range(len(klines)):
					price2.append( float(klines[0][4])/float(klines[j][4]) )	
	
		if len(price1)==0:
			price1 = list( np.ones(len(price2)) )	
		if len(price2)==0:
			price2 = list( np.ones(len(price1)) )	
			
		if len(price1) == len(price2):
			for j in range(len(price1)):
#				synthetic_price.append( ( 0.5 * price1[j] + 0.5 * price2[j] ) * math.pow( 1.0 + apd, j ) )	
				synthetic_price.append( ( 0.5 * price1[j] + 0.5 * price2[j] ) )	
	
#		print( names[it], apd, apy[it] / 100.0 )
		if len(synthetic_price) > 0:
			full_names.append( names[it] )
			full_prices.append( synthetic_price )

	sizes_list = []
	for it in range(len(full_names)):
		sizes_list.append( len(full_prices[it]) )
	counts = np.bincount( np.array(sizes_list) )
	ref_size = np.argmax( counts )

	final_names = []
	final_prices = []
	for it in range(len(full_names)):
		if len(full_prices[it]) == ref_size:
			final_names.append( full_names[it] )
			final_prices.append( full_prices[it] )

	full_names = np.array(final_names)
	full_prices = np.array(final_prices).T
	
	df_assets_opt = pd.DataFrame( data=full_prices, index=list(np.arange(full_prices.shape[0])), columns=list(full_names) )
	#print( df_assets_opt )

	sharpe, weights = opt_weights( df_assets_opt )
	print( weights )

	send_message( full_names, weights )


compute_weights(7)
'''
while True:

	try:
		compute_weights(7)
	except:
		pass
	time.sleep(60 * 60 * 12)
'''




