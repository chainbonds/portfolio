import requests
import pandas as pd

atrix_pools = requests.get("https://api.atrix.finance/api/pools",auth=('user', 'pass')).json()["pools"]#["data"]


num_pools = len(atrix_pools)

d = {"id":[],"created_at":[],"coin_mint":[],"pc_mint":[],
     "market":[], "open_orders":[],
     "pool_coin_account":[],
     "pool_pc_account":[],
     "pool_lp_account":[],
     "lp_mint":[]}

for i, pool in enumerate(atrix_pools):
    id = pool["id"]
    created_at = pool["created_at"]
    coin_mint = pool["coin_mint"] # mint addr of token
    pc_mint = pool["pc_mint"] # mint addr of other token in pool
    market_addr = pool["market"] # market tells you amount of each token in pool, tvl and volume
    open_orders_addr = pool["open_orders"] # this is serum dex specific. It creates an open orders account where the the orders which are waiting to be fulfilled sit
    pool_coin_account = pool["pool_coin_account"] # dont know what this 2 do. the amounts dont match the market....
    pool_pc_account = pool["pool_pc_account"] # dont know what this 2 do.

    # these two track the amount of lp tokens minted for this pool I think.
    # might be useful for figuring out apy
    pool_lp_account = pool["pool_lp_account"] #
    lp_mint = pool["lp_mint"]

    d["id"].append(id)
    d["created_at"].append(created_at)
    d["coin_mint"].append(coin_mint)
    d["pc_mint"].append(pc_mint)
    d["market"].append(market_addr)
    d["open_orders"].append(open_orders_addr)
    d["pool_coin_account"].append(pool_coin_account)
    d["pool_pc_account"].append(pool_pc_account)
    d["pool_lp_account"].append(pool_lp_account)
    d["lp_mint"].append(lp_mint)



df = pd.DataFrame(data=d)
df.to_pickle("./atrix_scraper/data/atrix_pools.pkl")

