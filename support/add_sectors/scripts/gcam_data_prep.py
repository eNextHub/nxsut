#%% 
import pandas as pd

mixes = {
    'Steel': {
        'sheet_name': 'SteelProdTech',
        'regions': {
            'EU-15': ['IT','ES','PT','FR','BE','LU','NL','DE','DK','SE','FI','AT','IE','GR','MT'],
            'EU-12': ['PL','CZ','SK','SI','HU','RO','BG','HR','LT','LV','EE','CY'],
            
        },
        'variables': {
            'Production|Steel|BF_BOF':'Manufacture of basic iron and steel and of ferro-alloys and first products thereof',
            'Production|Steel|EAF_scrap_fossil_NG_finish':'Re-processing of secondary steel into new steel',
            'Production|Steel|DRI_EAF_NG':'DRI-EAF-NG',
            'Production|Steel|DRI_SAF_BOF_NG':'DRI-SAF-BOF-NG',
            'Production|Steel|BF_BOF_BECCSmax':'BF-BOF-BECCSmax',
            'Production|Steel|BF_BOF_BECCSmin':'BF-BOF-BECCSmin',
            'Production|Steel|BF_BOF_CCS_73%':'BF-BOF-CCS-73%',
            'Production|Steel|BF_BOF_CCS_86%':'BF-BOF-CCS-86%',
            'Production|Steel|DRI_EAF_BECCS':'DRI-EAF-BECCS',
            'Production|Steel|DRI_EAF_H2':'DRI-EAF-H2',
            'Production|Steel|DRI_EAF_NG_CCS':'DRI-EAF-NG-CCS',
            'Production|Steel|DRI_EAF_coal_CCS':'DRI-EAF-COAL-CCS',
            'Production|Steel|DRI_SAF_BOF_BECCS':'DRI-SAF-BOF-BECCS',
            'Production|Steel|DRI_SAF_BOF_H2':'DRI-SAF-BOF-H2',
            'Production|Steel|EAF_scrap_bio_NG_finish':'Re-processing of secondary steel into new steel',
            'Production|Steel|SR_BOF':'SR-BOF',
            'Production|Steel|SR_BOF_CCS':'SR-BOF-CCS',
            'Production|Steel|MOE':'MOE',
            'Production|Steel|AEL_EAF':'AEL-EAF',
            'Production|Steel|EAF_scrap_bio_elec_finish':'Re-processing of secondary steel into new steel',
            'Production|Steel|EAF_scrap_fossil_elec_finish':'Re-processing of secondary steel into new steel',
        }
    },
    'Electricity': {
        'sheet_name': 'full_data',
        'regions': {
            'EU-15': ['IT','ES','PT','FR','BE','LU','NL','DE','DK','SE','FI','AT','IE','GR','MT'],
            'EU-12': ['PL','CZ','SK','SI','HU','RO','BG','HR','LT','LV','EE','CY'],
        },
        'variables': {
            'Secondary Energy|Electricity|Biomass':'Bioenergy',
            'Secondary Energy|Electricity|Coal':'Coal',
            'Secondary Energy|Electricity|Gas':'Gas',
            'Secondary Energy|Electricity|Hydro':'Hydro',
            'Secondary Energy|Electricity|Geothermal':'Other Renewables',
            'Secondary Energy|Electricity|Nuclear':'Nuclear',
            'Secondary Energy|Electricity|Oil':'Other Fossil',
            'Secondary Energy|Electricity|Solar':'Solar',
            'Secondary Energy|Electricity|Wind':'Wind',
        }
    }
}

exio_reg_map = {
    'Africa_Eastern': 'WF',
    'Africa_Northern': 'WF',
    'Africa_Southern': 'WF',
    'Africa_Western': 'WF',
    'Argentina': 'WL',
    'Australia_NZ':'AU',
    'Brazil':'BR',
    'Canada':'CA',
    'Central America and Caribbean':'WL',
    'Central Asia':'WA',
    'China':'CN',
    'Colombia':'WL',
    'Europe_Eastern':'WE',
    'Europe_Non_EU':'WE',
    'European Free Trade Association':'NO',
    'India':'IN',
    'Indonesia':'ID',
    'Japan':'JP',
    'Mexico':'MX',
    'Middle East':'WM',
    'Pakistan':'WA',
    'Russia':'RU',
    'South Africa':'ZA',
    'South America_Northern':'WL',
    'South America_Southern':'WL',
    'South Asia':'WA',
    'South Korea':'KR',
    'Southeast Asia':'WA',
    'Taiwan':'WA',
    'USA':'US',
    }



scenarios = ['NDC_LTT','NDC_LTT_CBAM','NDC_LTT_CBAM-G_SUBS','NDC_LTT_CBAM-G_SUBS_HI']
path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/IAM COMPACT Study 9/Data/GCAM/GCAM data.xlsx'
indices = ['Scenario','Region','Variable']
to_drop = ['Model','Unit']

# %%
for commodity,info in mixes.items():
    df = pd.read_excel(path,sheet_name=info['sheet_name'])
    df = df.query("Scenario in @scenarios & Variable in @info['variables'].keys()") 
    df = df.drop(columns=to_drop)
    
    df['Variable'] = df['Variable'].map(info['variables'])
    df.set_index(indices,inplace=True)

    df = df.div(df.groupby(['Scenario', 'Region']).transform('sum'))
    df = df.groupby(indices).sum()

    df = df.replace(0, 1e-8)
    df.to_excel("{}_mixes.xlsx".format(commodity))

# final demand
variables = ['Consumption|Steel','Exports|Steel']
df = pd.read_excel(path,sheet_name='EUSteel')
df = df.query("Variable in @variables") 
df = df.drop(columns=to_drop)
df.set_index(indices,inplace=True)
df = df.groupby(['Scenario','Region']).sum()
df *= 1e6 # Mton to ton
df.to_excel("Steel_consumption.xlsx")

# %%
import pandas as pd

path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/IAM COMPACT Study 9/Data/GCAM/GCAM_EU_Imports.xlsx'

imports = pd.read_excel(path).fillna(0)

imports[['Type', 'Commodity', "Region_from", "Technology"]] = imports['Variable'].str.split('|', n=3, expand=True)
imports = imports.drop(columns=['Type', 'Model', 'Commodity'])
imports['Region_from'] = imports['Region_from'].map(exio_reg_map)  
imports = imports.set_index(['Scenario', 'Region', 'Region_from', 'Unit','Technology'])
imports = imports.groupby(level=['Scenario', 'Region', 'Region_from', 'Unit']).sum(numeric_only=True)
imports.columns.names = ['Year']
imports = imports.stack().to_frame()
imports.columns = ['Value']
imports = imports.reset_index()

path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/IAM COMPACT Study 9/Data/GCAM/GCAM data.xlsx'
dom_share = pd.read_excel(path, sheet_name='EUDomesticShare')

# Calculate total imports per Scenario and Year
total_imports = imports.groupby(['Scenario', 'Year'])['Value'].transform('sum')
# Calculate percentage share for each Region_from
imports['Value'] = imports['Value'] / total_imports


for year in imports['Year'].unique():
    for scenario in imports['Scenario'].unique():
        # Get the domestic share for the current year and scenario
        intyear = int(year)
        domestic_share = dom_share.query("Year == @intyear & Scenario == @scenario")['Value'].values[0]
        # Apply the domestic share to the imports
        imports.loc[(imports['Year'] == year) & (imports['Scenario'] == scenario), 'Value'] *= (1-domestic_share)

        # Append the domestic share as a new row for EU
        row = {
            'Scenario': scenario,
            'Region': 'EU',
            'Region_from': 'EU',
            'Unit': 'Mt',
            'Technology': None,
            'Year': year,
            'Value': domestic_share
        }
        imports = pd.concat([imports, pd.DataFrame([row])], ignore_index=True)

imports['Region'] = 'EU-12'
imports_EU15 = imports.copy()
imports_EU15['Region'] = 'EU-15'
imports = pd.concat([imports, imports_EU15], ignore_index=True)

imports.reset_index(inplace=True)
imports = imports.drop(columns=['Technology','index'])

imports.to_excel("Steel_imports.xlsx", index=False)




#%%