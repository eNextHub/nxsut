#%%
import pandas as pd
import country_converter as coco

def map_ember_to_classification(
        path:str,
        classification:str,
        mode:str=None,
        year:int=None,
):

    df = pd.read_csv(path)
    df = df.query(
        'Category=="Electricity generation" & \
        `Country code`.notna() & \
        Subcategory=="Fuel" & \
        Unit=="TWh"'
    )

    df['Region'] = coco.convert(
        names=df['Country code'],
        to=classification
    )

    df.set_index(['Region','Year','Variable'], inplace=True)
    df = df['Value']
    df = df.groupby(['Region','Year','Variable']).sum()
    df = df.to_frame()
    df.columns = ['Value'] 

    if year is not None:
        df = df.loc[(slice(None),year,slice(None)),:]

    if mode=='mix':
        df = df.groupby(level=[0,1]).apply(lambda x: x / x.sum())
        df = df.droplevel(0,axis=0)
        df = df.droplevel(0,axis=0)
        return df

    else:
        return df

# %%
