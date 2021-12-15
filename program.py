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
	now_milli = int(round(time.time() * 1000))
	one_quarter_milli = int( 31556952000 )

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

	r = requests.get('https://api.raydium.io/pairs').json()

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

	full_names = np.array(full_names)
	full_prices = np.array(full_prices).T
	
	df_assets_opt = pd.DataFrame( data=full_prices, index=list(np.arange(full_prices.shape[0])), columns=list(full_names) )
	#print( df_assets_opt )

	sharpe, weights = opt_weights( df_assets_opt )
	print( weights )

	send_message( full_names, weights )


while True:
	try:
		compute_weights(7)
	except:
		pass
	time.sleep(60 * 60 * 12)




