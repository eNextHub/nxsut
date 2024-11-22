#%% 
import mario
import yaml

user = 'LR'   # change this to your username

with open('paths.yml', 'r') as file: # open the yml file
    paths = yaml.safe_load(file)

db = mario.parse_from_txt(
    path = f"{paths[user]['export']}/flows", 
    table = 'SUT', 
    mode = 'flows'
    )

#%%
ee_act = ['Coal','Gas','Other Fossil','Bioenergy','Hydro','Wind','Solar','Nuclear','Other Renewables']
ghgs = ['Carbon dioxide, fossil (air - Emiss)','CH4 (air - Emiss)','N2O (air - Emiss)']

e = db.e.loc[ghgs,(slice(None),'Activity',ee_act)]
e.loc['CH4 (air - Emiss)',:] *= 29.8
e.loc['N2O (air - Emiss)',:] *= 273

e = e.sum(0)

# %%
f = db.f.loc[ghgs,(slice(None),'Activity',ee_act)]
f.loc['CH4 (air - Emiss)',:] *= 29.8
f.loc['N2O (air - Emiss)',:] *= 273

f = f.sum(0)
# %%
