#!/usr/bin/env python
# coding: utf-8

# ### This notebooks builds 2 csv files for any commodity that you specify in the variable `SYMBOL_TO_RESEARCH`
# 
# The csv files are then written to as follows:
# ```
# df_iv_final.to_csv(f'./temp_folder/df_iv_final_{SYMBOL_TO_RESEARCH}.csv',index=False)
# df_iv_skew.to_csv(f'./temp_folder/df_iv_skew_{SYMBOL_TO_RESEARCH}.csv',index=False)
# ```
# 
# They can be copied to the volgrid project to be used by the Dash server that displays skew graphs for ES, CL, CB (Brent), and NG.

# In[1]:


import zipfile
import glob
import pandas as pd
import numpy as np
import pdb
from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
import sys
import os
if  not './' in sys.path:
    sys.path.append('./')
if  not '../' in sys.path:
    sys.path.append('../')

from barchartacs import build_db
from barchartacs import db_info
from barchartacs import plotly_utilities as pu
from barchartacs import cme_expirations as cmeexp
import plotly.graph_objs as go
from plotly.offline import  init_notebook_mode, iplot
init_notebook_mode(connected=True)
import plotly.tools as tls
from plotly.subplots import make_subplots

from plotly.graph_objs.layout import Font,Margin
from IPython import display

import datetime
import io
from tqdm import tqdm,tqdm_notebook
from barchartacs import pg_pandas as pg
import mibian
import py_vollib
import importlib
from py_vollib import black
from py_vollib.black import implied_volatility
import traceback
import db_info
MONTH_CODES = 'FGHJKMNQUVXZ'
DICT_MONTH_NUMS = {MONTH_CODES[i]:i+1 for i in range(len(MONTH_CODES))}

# importlib.reload(db_info)


# In[2]:


import warnings
warnings.filterwarnings('ignore')


# ### important global variables

# In[3]:



DEBUG_IT=False
opttab = 'sec_schema.options_table'
futtab = 'sec_schema.underlying_table'
pga = db_info.get_db_info()
SYMBOL_TO_RESEARCH = 'ES'
STRIKE_DIVISORS = {}

# df_expiry_dates_additions = pd.read_csv('df_expiry_dates_additions.csv')
df_expiry_dates_additions = pd.read_csv('live_option_expirations.csv')


# ### methods to build options

# In[4]:


def _get_contract_number_from_symbol(symbol):
    c = symbol[0:2]
    if c in ['CL','ES','NG']:
        return 2
    return 2


# In[5]:


USE_PYVOL = True
def lam_pyvol(r):
    try:
        return implied_volatility.implied_volatility(r.close_x,r.close_y,r.strike,.02,r.dte/365, r.pc.lower())
    except:
        return -1
# lam_pyvol = lambda r:implied_volatility.implied_volatility(r.close_x,r.close_y,r.strike,.02,r.dte/365, r.pc.lower())
lam_mibian = lambda r:mibian.BS([r.close_y,r.strike,2,r.dte], callPrice=r.close_x).impliedVolatility

def get_implieds(df,df_expiry_dates,contract):
    df2 = df[['symbol','contract_num','pc','settle_date','strike','close_x','close_y']]
    df2 = df2[(((df2.pc=='C' )& (df2.strike>=df2.close_y)) | ((df2.pc=='P' ) & (df2.strike<df2.close_y)))  & (df2.symbol.str.contains(contract))]
    cnum = _get_contract_number_from_symbol(contract)
    df2 = df2[df2.contract_num==2]
    phigh = df2.close_y.max()
    plow = df2.close_y.min()
    high_strike = round(phigh * 1.3)
    low_strike = round(plow * .7)
    df2 = df2[(df2.strike>=low_strike) & (df2.strike<=high_strike)]

    df9 = df2[df2.symbol==contract]
    df9 = df9.merge(df_expiry_dates.rename(columns={'settle_date':'expiry'}),on='symbol',how='inner')
    df9['syear'] = df9.settle_date.astype(str).str.slice(0,4).astype(int)
    df9['smon'] = df9.settle_date.astype(str).str.slice(4,6).astype(int)
    df9['sday'] = df9.settle_date.astype(str).str.slice(6,8).astype(int)
    df9['eyear'] = df9.expiry.astype(str).str.slice(0,4).astype(int)
    df9['emon'] = df9.expiry.astype(str).str.slice(4,6).astype(int)
    df9['eday'] = df9.expiry.astype(str).str.slice(6,8).astype(int)
    df9['sdatetime'] = df9.apply(lambda r:datetime.datetime(r.syear,r.smon,r.sday),axis=1)
    df9['edatetime'] = df9.apply(lambda r:datetime.datetime(r.eyear,r.emon,r.eday),axis=1)
    df9['dte'] = df9.edatetime - df9.sdatetime
    df9.dte = df9.dte.dt.days
    df9 = df9[['symbol','settle_date','pc','contract_num','strike','close_x','close_y','dte']]
    df10 = df9.iloc[:len(df9)].copy()
    df10.index = list(range(len(df10)))
    if USE_PYVOL:
        df10['iv'] = df10.apply(lam_pyvol,axis=1)
    else:
        n = 100
        for i in tqdm_notebook(np.arange(0,len(df10)-n,n)):
                df10.loc[i:i+n,'iv'] = df10.loc[i:i+n].apply(lam_mibian,axis=1)
        print(f'doing remaining {datetime.datetime.now()}')
        i = df10[df10.iv.isna()].index[0]
        df10.loc[i:,'iv'] = df10.loc[i:].apply(lam_mbian,axis=1)
        print(f'done with remaining {datetime.datetime.now()}')
    return df10


# #### example of using mibian for options calcs (we use py_vollib instead)

# In[6]:


def _test_mibian():
    underlying=1.4565
    strike=1.45
    interest = 1
    days=30
    opt_info = [underlying,strike,interest,days]
    c = mibian.BS(opt_info, volatility=20)
    print(c.callPrice,
    c.putPrice,
    c.callDelta,
    c.putDelta,
    c.callDelta2,
    c.putDelta2,
    c.callTheta,
    c.putTheta,
    c.callRho,
    c.putRho,
    c.vega,
    c.gamma)


    co = mibian.BS(opt_info, callPrice=c.callPrice)
    co.impliedVolatility


# #### Show simple example of using py_vol package

# In[7]:


def _test_py_vollib():
    #CL,Q2019,560P,07/02/2019,0.6,1.61,0.54,1.54,1997,4465
    F = 56.25
    K = 56
    sigma = .366591539
    flag = 'p'
    t = 15/365.0
    r = .025
    discounted_call_price = black.black(flag, F, K, t, r, sigma)
    dcp = 1.54
    ivpy = implied_volatility.implied_volatility(dcp, F, K, r, t, flag)
    ivmn = mibian.BS([F,K,2.5,15], callPrice=dcp).impliedVolatility
    discounted_call_price,ivpy,ivmn


# #### Define method to get a contract from postgres

# In[8]:


def _next_monthyear_code(contract):
    code_val = contract[-3]
    code_num = DICT_MONTH_NUMS[code_val]
    y = int(contract[-2:])
    if code_num+1>12:
        next_code_num = 1
        next_y = y + 1
    else:
        next_code_num = code_num+1
        next_y = y
    next_code_val = MONTH_CODES[next_code_num-1]
    next_contract = contract[0:-3] + next_code_val + '%02d' %(next_y)
    return next_contract

def get_symbol_expiries(df,symbol_col='symbol',is_option=True):
    all_syms = df[symbol_col].unique()
    all_expiries = [cmeexp.get_expiry(s,is_option=is_option) for s in all_syms]
    all_expiries = [d.strftime('%Y%m%d') for d in all_expiries]
    return pd.DataFrame({'symbol':all_syms,'settle_date':all_expiries})

def get_postgres_data(contract,strike_divisor=None):
    '''
    Get options and underlying data for ONLY ONE CONTRACT
    '''
    osql = f"select * from {opttab} where symbol='{contract}';"
    dfo = pga.get_sql(osql)
    if len(dfo)<10:
        e = f'''
        get_postgres_data ERROR: not enough option data for contract {contract} 
        '''
        raise ValueError(e)
    num_settle_days = len(dfo.settle_date.unique())
    u_contract = contract
    for i in range(12):
        usql = f"select * from {futtab} where symbol='{u_contract}';"
        dfu = pga.get_sql(usql)
        if len(dfu) < num_settle_days:
            u_contract = _next_monthyear_code(u_contract)
            print(f'trying contract {u_contract}')
        else:
            break

    if len(dfu)< num_settle_days:
        e = f'''
        get_postgres_data ERROR: not enough underlying days found for options contract {contract} 
        where len(underlying) = {len(dfu)} and num_settle_days = {num_settle_days}
        '''
        raise ValueError(e)
    # Merge options and futures data
    dfu = dfu.rename(columns={'symbol':'u_symbol'})
    df = dfo.merge(dfu,how='inner',on=['settle_date'])
    # Get options expiration dates
#     df_expiry_dates = dfo[['symbol','settle_date']].groupby('symbol',as_index=False).max()
#     df_expiry_dates = dfo[['symbol','settle_date']]
#     df_additions = df_expiry_dates_additions[df_expiry_dates_additions.symbol==contract]
#     df_additions = df_additions[['symbol','yyyymmdd_option']].rename(columns={'yyyymmdd_option':'settle_date'})
#     additional_symbols = df_additions.symbol.values
#     df_expiry_dates = df_expiry_dates[~df_expiry_dates.symbol.isin(additional_symbols)]
#     df_expiry_dates = df_expiry_dates.append(df_additions).sort_values('symbol').copy()
    df_expiry_dates = get_symbol_expiries(dfo)
    if strike_divisor is not None:
        df.strike = df.strike/strike_divisor
    return df,df_expiry_dates


# ### Use py_vol to get options skews by percent in/out of the money (moneyness)

# #### Add in even "amount in/out the money strikes, and interpolate their implied vols and skews

# In[9]:


def get_even_moneyness_strikes(df10):
    # define amounts around the money which will help create strikes to add
    moneyness = np.arange(.7,1.4,.05).round(6)
    # define columns on which to execute groupby
#     gb_cols = ['symbol','settle_date','pc','contract_num','dte','close_y']
    gb_cols = ['symbol','settle_date','contract_num','dte','close_y']
    # define function used in groupby.apply to create strikes and iv's at those strikes
    #   where the strikes are an even amount from the money 
    #   (like .7, .8, ... 1, 1.1, 1.2, etc)
    def _add_even_moneyness_strikes(df):
        # get underlying from first row (the groupby makes them all the same)
        r = df.iloc[0]
        underlying = r.close_y
        # create new rows to append to df, using only the gb_cols
        df_ret1 = df.iloc[:len(moneyness)][gb_cols].copy()
        # add nan iv's !!!! MUST BE np.nan - NOT None
        df_ret1['iv'] = np.nan
        # add new strikes
        df_ret1['strike'] = moneyness * underlying
        # append the new strikes
        try:
            # try with using the sort=True options for versions of pandas after 0.23
            dfa = df.append(df_ret1,ignore_index=True,sort=True).copy()
        except:
            # otherwise do not specify sort
            dfa = df.append(df_ret1,ignore_index=True).copy()
        df_ret2 = dfa.sort_values(['symbol','settle_date','pc','strike'])
        df_ret2 = df_ret2.drop_duplicates(subset='strike')
        # set the index to the strike so that interpolate works
        df_ret2.index = df_ret2.strike
        # create interpolated iv's
        df_ret2['iv'] = df_ret2.iv.interpolate(method='polynomial', order=2)
        # reset the index
        df_ret2.index = list(range(len(df_ret2)))
        return df_ret2

    # start here
    df11 = df10.groupby(gb_cols).apply(_add_even_moneyness_strikes).copy()
    df11.index = list(range(len(df11)))
    df11['moneyness'] = df11.strike / df11.close_y
    df11.moneyness = df11.moneyness.round(4)

    df12 = df11[(df11.moneyness.isin(moneyness)) & (~df11.iv.isna())].copy()
    df12.moneyness  = df12.moneyness - 1
    df12.index = list(range(len(df12)))
    df12_atm = df12[df12.moneyness==0][['symbol','settle_date','pc','iv']]
    df12_atm = df12_atm.rename(columns={'iv':'atm_iv'})
    
    df12_atm = df12_atm.drop_duplicates()
    df12_atm.pc = ''#np.nan
    df12.pc = ''#np.nan

    df12 = df12.merge(df12_atm,on=['symbol','settle_date','pc'],how='inner')

    df12.moneyness = df12.moneyness.round(4)
    df12['vol_skew'] = (df12.iv - df12.atm_iv).round(4)
    return df12


# #### get all contracts in the options database

# In[10]:


all_contracts = pga.get_sql(f"select distinct symbol from {opttab} where symbol~'^{SYMBOL_TO_RESEARCH}'").sort_values('symbol').values.reshape(-1)
len(all_contracts)


# #### show last dates

# In[11]:


def create_skew_per_date_df(df):
    '''
    Find the first settle_date whose count of rows is equal to max count of rows.
    df: DataFrame from df_iv_final_SS.csv, where SS is like ES, CL, NG, etc.
         df contains data for ONLY ONE SYMBOL
    '''
    # get the first symbol (which should be the only symbol)
    contract = df.symbol.unique()[0]
    # get just that symbol's data
    df12 = df[df.symbol==contract]
    df_counts = df12[['settle_date','moneyness']].groupby('settle_date',as_index=False).count()
    max_count = df_counts.moneyness.max()
    first_max_count_settle_date = df_counts[df_counts.moneyness==max_count].iloc[0].settle_date

    df_ret2 = df12[df12.settle_date==first_max_count_settle_date][['moneyness']]
    all_settle_dates = sorted(df_counts.settle_date.unique())
    for settle_date in all_settle_dates:
        df_temp = df12[df12.settle_date==settle_date][['moneyness','vol_skew']]
        df_ret2 = df_ret2.merge(df_temp,on='moneyness',how='outer')
        df_ret2 = df_ret2.rename(columns={'vol_skew':str(settle_date)})
    df_ret2 = df_ret2.sort_values('moneyness')
    df_ret2.index = list(range(len(df_ret2)))
    df_ret3 = df_ret2.fillna(0)
    df_ret3['csum'] = df_ret3.apply(lambda r: sum([r[c] for c in df_ret2.columns.values]),axis=1)
    df_csum = df_ret3[['moneyness','csum']].groupby('moneyness',as_index=False).max()
    df_ret4 = df_ret3.merge(df_csum,how='inner',on=['moneyness','csum']).drop_duplicates()
    df_ret4.index = list(range(len(df_ret4)))
    
    # eliminate csum column from returned DataFrame
    df_ret4 = df_ret4[[c for c in df_ret4.columns.values if 'csum' not in c]]
    
    # convert zero values to np.NaN, for those Out of the Money columns
    for col in [c for c in df_ret4.columns.values if 'moneyness' not in c]:
        df_ret4[col] = df_ret4[col].apply(lambda v: np.NaN if v==0.0 else v)
    df_ret4[df_ret4.moneyness==0] = 0.0
    return df_ret4


# ### Skew per contract

# In[12]:


def skew_per_symbol(symbol,strike_divisor=None):
    '''
    For a symbol like CLM16 or EZH19, create 2 Dataframes
      1. df_iv - contains rows of implied vols, for only the 'pseudo' strikes that are an even
                 percent away from the money for each settle_date
      2. df_skew - contains one row per day of skew data of for 'pseudo' strikes that are an even
                 percent away from the money for each settle_date
    '''
    _exception = None
    _stacktrace = None
    df_iv = None
    df_skew = None
    try:
        df,df_expiry_dates = get_postgres_data(symbol)
        if len(df[df.contract_num==2])>0:
            df10 = get_implieds(df,df_expiry_dates,symbol)
            df12 = get_even_moneyness_strikes(df10)
            df_sk = create_skew_per_date_df(df12)
            df_sk.index = list(range(len(df_sk)))
            df_skt = df_sk.T
            df_skt.columns = df_skt.loc['moneyness']
            df_skt = df_skt.iloc[1:].copy()
            df_skt['symbol'] = symbol
            df_skt['settle_date'] = df_skt.index
            df_iv = df12.copy() 
            df_skew = df_skt.copy()
    except Exception as e:
        _exception = str(e)
        _stacktrace = traceback.format_exc()
    return df_iv,df_skew,_exception,_stacktrace


# ### Show contracts

# ## MAIN LOOP
# #### Loop through all contracts and create DataFrames for implied vol and skew (`df_iv_final` and `df_iv_skew`)

# In[13]:


if __name__=='__main__':
    for sym_to_res in tqdm_notebook(['ES','CL','NG']):
        SYMBOL_TO_RESEARCH = sym_to_res
        print(f"processing commodity: {SYMBOL_TO_RESEARCH}")
        all_contracts = pga.get_sql(f"select distinct symbol from {opttab} where symbol~'^{SYMBOL_TO_RESEARCH}'").sort_values('symbol').values.reshape(-1)
        strike_div = None if SYMBOL_TO_RESEARCH not in STRIKE_DIVISORS.keys() else STRIKE_DIVISORS[SYMBOL_TO_RESEARCH]
        df_iv_final = None
        df_iv_skew = None
        dict_exceptions = {}
        dict_stacktraces = {}
        contracts = all_contracts
        if SYMBOL_TO_RESEARCH in ['ES','GE']:
            contracts = [c for c in all_contracts if c[-3] in ['H','M','U','Z']]
        for contract in tqdm_notebook(contracts):
            df12,df_skew,_exception,_stacktrace = skew_per_symbol(contract,strike_divisor=strike_div)
            if _exception is not None:
                dict_exceptions[contract] = _exception
                dict_stacktraces[contract] = _stacktrace
                continue

            if (df12 is None or len(df12)<1) or (df_skew is None or len(df_skew)<1):
                if (df12 is None or len(df12)<1):
                    dict_exceptions[contract] = "No data returned for df in skew_per_symbol"
                if (df_skew is None or len(df_skew)<1):
                    dict_exceptions[contract] = "No data returned for df_skew in skew_per_symbol"
                continue
            if df12 is not None:
                if df_iv_final is None:
                    df_iv_final = df12.copy()
                else:
                    df_iv_final = df_iv_final.append(df12,ignore_index=True)
                if df_iv_skew is None:
                    df_iv_skew = df_skew.copy()
                else:
                    df_iv_skew = df_iv_skew.append(df_skew,ignore_index=True)
                    df_iv_skew.index = list(range(len(df_iv_skew)))

        df_iv_final = df_iv_final.sort_values(['settle_date','moneyness'])
        print(dict_exceptions)
        df_iv_final.to_csv(f'./temp_folder/df_iv_final_{SYMBOL_TO_RESEARCH}.csv',index=False)
        df_iv_skew.to_csv(f'./temp_folder/df_iv_skew_{SYMBOL_TO_RESEARCH}.csv',index=False)    


# ### save to csv and print any exceptions that might have occured

# In[14]:


# print(dict_exceptions)
# df_iv_final.to_csv(f'./temp_folder/df_iv_final_{SYMBOL_TO_RESEARCH}.csv',index=False)
# df_iv_skew.to_csv(f'./temp_folder/df_iv_skew_{SYMBOL_TO_RESEARCH}.csv',index=False)


# # CODE ENDS HERE FOR BUILD

# In[15]:


# !jupyter nbconvert --to script step_04_build_df_iv_skew_csvs.ipynb


# ## END

# In[ ]:





# In[ ]:




