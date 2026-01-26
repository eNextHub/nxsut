#%%
import os
import mario
import pandas as pd
import yaml
from entsoe import EntsoeRawClient
from entsoe.mappings import NEIGHBOURS

user = 'LR'
past_year = 2024

with open('paths.yml', 'r') as file: # open the yml file
    paths = yaml.safe_load(file)

client = EntsoeRawClient(api_key="d64a15d0-7a32-415e-9894-7780deb8a05c")

#%% parse eNextSUT from past year
db = mario.parse_from_txt(paths[user]['raw'], table='SUT', mode='flows')

#%% Aggregate electricity commodities and activities to match EMBER
db.aggregate("support/aggregate_ee.xlsx",ignore_nan=True)

#%% Import electricity mixes from EMBER
from support.ember_remapping import map_ember_to_classification

ee_mix = map_ember_to_classification(
    path = paths[user]['ember'],
    classification = 'EXIO3',
    year = None,
    mode = 'mix',
)

#%% Update electricity mixes
z = db.z
s = db.s

for region in db.get_index('Region'):
    print(region,end=' ')
    region_latest_year = ee_mix.loc[(region,slice(None),slice(None))].index.get_level_values(0).max()
    new_mix = ee_mix.loc[(region,region_latest_year,slice(None)),'Value'].to_frame().sort_index(axis=0)
    # new_mix = ee_mix.loc[(region,slice(None),slice(None)),'Value'].to_frame().sort_index(axis=0) 
    new_mix.index = new_mix.index.get_level_values(2)
    old_market_share = s.loc[(region, 'Activity', new_mix.index),(region,'Commodity','Electricity')].sum().sum()
    
    s.loc[(region, 'Activity', new_mix.index),(region,'Commodity','Electricity')] = new_mix.values*old_market_share # check if commodity electricity is called "Electricity" in aggregation excel file
    # s.loc[:,(region,'Commodity','Electricity')] /= s.loc[:,(region,'Commodity','Electricity')].sum()
    print('done')

z.update(s)

db.update_scenarios('baseline',z=z)
db.reset_to_coefficients('baseline')

#%%
# db.get_add_sectors_excel("support/add_sectors.xlsx")

# %%    
db.read_add_sectors_excel(
    path="support/add_sectors.xlsx",
    read_inventories=True,
    )

# %%
db.add_sectors()

# %% Shock on the use side: 
# "Electricity supply" activity must come consume only domestic "electricity" commodity
# "Electricity" commodity consumption (both domestic and imported) must be transferred to domestic "Electricity need" consumption
u_new = db.u.copy()
z_new = db.z.copy()

u_new.loc[:,(slice(None),"Activity","Electricity supply")] *= 0

for region in db.get_index("Region"):
    u_new.loc[(region,"Commodity","Electricity"),(region,"Activity","Electricity supply")] = 1

    ee_consumption = db.u.loc[(slice(None),"Commodity","Electricity"),(region,"Activity",slice(None))].sum(0).to_frame().T
    ee_consumption.index = pd.MultiIndex.from_arrays([[region],["Commodity"],["Electricity need"]],names=db.u.index.names)

    u_new.loc[(slice(None),"Commodity","Electricity"),(region,"Activity",slice(None))] *= 0
    u_new.update(ee_consumption)

z_new.update(u_new)

db.update_scenarios(scenario='baseline',z=z_new)
db.reset_to_coefficients('baseline')

# %% Shock on the supply side
# db.get_shock_excel(os.path.join(paths[user]['export'],str(past_year+1),"trades.xlsx"))
db.shock_calc(os.path.join(paths[user]['export'],str(past_year+1),"trades.xlsx"), z=True, scenario='ee_trades')

#%% Shock on the supply side
db.to_txt(
    path = os.path.join(paths[user]['export'],str(past_year+1)),
    scenario = 'ee_trades',
    # flows=True,
    # coefficients=True
    )

# %%
