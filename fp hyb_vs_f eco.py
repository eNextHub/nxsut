#%%
import mario
import pandas as pd

path_eco_sut = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase/Monetary/v3.8.2/MRSUT/MRSUT_2011.zip'
path_eco_mon = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase/Monetary/v3.8.2/IOT/IOT_2011_ixi.zip'
path_hyb_sut = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase/Hybrid/3.3.18_mario_with_va/flows'

#%% monetary parsing
eco_sut = mario.parse_exiobase(
    path = path_eco_sut,
    unit = 'Monetary',
    table = 'SUT',
    version = '3.8.2',
    )

eco_iot = mario.parse_exiobase(
    path = path_eco_mon,
    unit = 'Monetary',
    table = 'IOT',
    version = '3.8.2',
    )

#%% monetary SUT extension
E_iot = eco_iot.E
E_sut = eco_sut.E
new_E_sut = pd.DataFrame(0.0, index=E_iot.index, columns=E_sut.columns)

new_column_levels = pd.MultiIndex.from_arrays([
    E_iot.columns.get_level_values(0),
    ['Activity' for i in range(E_iot.shape[1])],
    E_iot.columns.get_level_values(2)
])

E_iot.columns = new_column_levels

new_E_sut.update(E_iot)

new_units_sut = eco_iot.units['Satellite account']

eco_sut.add_extensions(
    io=new_E_sut,
    units=new_units_sut.loc[new_E_sut.index], # We should only pass the items that are in the new_E_sut
    matrix='E'
)

#%% hybrid sut parsing
hyb_sut = mario.parse_from_txt(
    path = path_hyb_sut,
    table = 'SUT',
    mode = 'flows',
)

#%% calculation and comparison
import numpy as np

f_eco = eco_sut.f
f_hyb = hyb_sut.f
p_hyb = mario.calc_f(hyb_sut.v,hyb_sut.w).sum(0)

#%%
f_eco_co2 = f_eco.loc["CO2 - combustion - air",:]
f_hyb_co2 = f_hyb.loc["Carbon dioxide, fossil (air - Emiss)",:] 
fp_hyb_co2 = f_hyb_co2 * p_hyb

#%%

