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


#%%. Add new sectors for electricity supply and electricity need (MARIO stable version)
# db.get_add_sectors_excel(
#     new_sectors = ["Electricity supply"],
#     regions = db.get_index("Region"),
#     path ="support/add_sectors_activities.xlsx",
#     item = "Activity",
#     )

# db.get_add_sectors_excel(
#     new_sectors = ["Electricity need"],
#     regions = db.get_index("Region"),
#     path ="support/add_sectors_commodities.xlsx",
#     item = "Commodity",
#     )


# %%
db.add_sectors(
    new_sectors = ["Electricity supply"],
    regions = db.get_index("Region"),
    io ="support/add_sectors_activities.xlsx",
    item = "Activity",
    inplace = True,
)

db.add_sectors(
    new_sectors = ["Electricity need"],
    regions = db.get_index("Region"),
    io ="support/add_sectors_commodities.xlsx",
    item = "Commodity",
    inplace = True,
)

# %% Alternatively, using the MARIO development version:
# db.get_add_sectors_excel("add_sectors_new.xlsx")
# db.read_add_sectors_excel(
#     path="support/add_sectors.xlsx",
#     read_inventories=True,
#     )
# db.add_sectors()

#%%% Export
db.to_txt(
    path = os.path.join(paths[user]['export'],str(past_year+1)),
    )

# %% Shock on the use side: 
# "Supply" activity must consume only domestic "original" commodity
# Original commodity consumption (both domestic and imported) must be transferred to domestic "Need" commodity consumption (both for use and final demand)

traded_commodities = ['Electricity']

u_new = db.u.copy()
Y_new = db.Y.copy()

U = db.U.copy().loc[(slice(None),"Commodity",traded_commodities),:].groupby(level=[0],axis=1).sum()
Y = Y_new.loc[(slice(None),"Commodity",traded_commodities),:].groupby(level=[0],axis=1).sum()
UY = U + Y

z_new = db.z.copy()

trades_df = {}

for commodity in traded_commodities:
    trades_df[commodity] = pd.DataFrame()
    u_new.loc[:,(slice(None),"Activity",f"{commodity} supply")] *= 0
    oth_activities = [i for i in db.get_index("Activity") if i != f"{commodity} supply"]
    
    for region in db.get_index("Region"):
        u_new.loc[(region,"Commodity",commodity),(region,"Activity",f"{commodity} supply")] = 1

        ee_consumption_u = db.u.loc[(slice(None),"Commodity",commodity),(region,"Activity",oth_activities)].sum(0).to_frame().T
        ee_consumption_u.index = pd.MultiIndex.from_arrays([[region],["Commodity"],[f"{commodity} need"]],names=db.u.index.names)

        ee_consumption_Y = db.Y.loc[(slice(None),"Commodity",commodity),(region,"Consumption category",slice(None))].sum(0).to_frame().T
        ee_consumption_Y.index = pd.MultiIndex.from_arrays([[region],["Commodity"],[f"{commodity} need"]],names=db.Y.index.names)

        u_new.update(ee_consumption_u)
        Y_new.update(ee_consumption_Y)

        u_new.loc[(slice(None),"Commodity",commodity),(region,"Activity",oth_activities)] *= 0
        Y_new.loc[(slice(None),"Commodity",commodity),(region,"Consumption category",slice(None))] *= 0

        trades_df[commodity] = pd.concat([
            trades_df[commodity], 
            UY.loc[:,region]/UY.loc[:,region].sum()
        ], axis=1
        )

z_new.update(u_new)

#%% Shock on the supply side
# "Supply" activities must provide "need" commodity according to trades dataframe

s_new = db.s.copy()
for commodity in traded_commodities:
    trades_df[commodity].index = pd.MultiIndex.from_arrays([
        trades_df[commodity].index.get_level_values(0),
        ['Activity']*len(trades_df[commodity].index),
        [f"{commodity} supply"]*len(trades_df[commodity].index)],
        names=db.s.index.names)
    
    trades_df[commodity].columns = pd.MultiIndex.from_arrays([
        trades_df[commodity].columns,
        ['Commodity']*len(trades_df[commodity].columns),
        [f"{commodity} need"]*len(trades_df[commodity].columns)],
        names=db.s.columns.names)

    s_new.update(trades_df[commodity])

z_new.update(s_new)

#%% Update scenario and reset coefficients
db.update_scenarios(scenario='baseline',z=z_new, Y=Y_new)
db.reset_to_coefficients('baseline')

# %% Shock on the supply side
# db.get_shock_excel(os.path.join(paths[user]['export'],str(past_year+1),"trades.xlsx"))
db.shock_calc(os.path.join(paths[user]['export'],str(past_year+1),"trades.xlsx"), z=True, scenario='ee_trades', force_rewrite=True)

#%% Shock on the supply side
db.to_txt(
    path = os.path.join(paths[user]['export'],str(past_year+1)+"_new"),
    scenario = 'ee_trades',
    # flows=True,
    # coefficients=True
    )

