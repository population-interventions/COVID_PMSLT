
import math
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import os
import re

fileCreated = {}

############### Shared ###############

def OutputToFile(df, path, fileAppend):
    # Called like this. Splits each random seed into its own file.
    #for value in chunk.index.unique('rand_seed'):
    #    OutputToFile(chunk.loc[value], filename, value)
    if not fileCreated.get(path):
        fileCreated[path] = {}
    
    fullFilePath = path + '_' + str(fileAppend) + '.csv'
    if fileCreated.get(path).get(fileAppend):
        # Append
        df.to_csv(fullFilePath, mode='a', index=False, header=False)
    else:
        fileCreated[path][fileAppend] = True
        df.to_csv(fullFilePath, index=False) 


def LoadColumn(path, inName, indexCols):
    return pd.read_csv(path + '_' + inName + '.csv',
                header=[0],
                index_col=list(range(indexCols)))


def Output(path, df):
    index = df.index.to_frame(index=False)
    index = index.drop(columns=['run', 'global_transmissibility'])
    df.index = pd.MultiIndex.from_frame(index)
    df = df.rename('value')
    
    # Consider the following as a nicer replacement:
    #"for name, subDf in df.groupby(level=0):"
    for value in index.rand_seed.unique():
        rdf = df[df.index.isin([value], level=0)]
        rdf = rdf.reset_index()
        rdf = rdf.drop(columns='rand_seed')
        OutputToFile(rdf, path, value)


############### Step 1 ###############

def GetCohortData(cohortFile):
    df = pd.read_csv(cohortFile + '.csv', 
                index_col=[0],
                header=[0])
    df.index.rename('cohort', True)
    df = df.reset_index()
    df['cohort'] = df['cohort'].astype(int)
    df['age'] = df['age'].astype(int)
    return df


def ProcessChunk(df, chortDf, typeAppend):
    df.columns.set_levels(df.columns.levels[1].astype(int), level=1, inplace=True)
    df.columns.set_levels(df.columns.levels[2].astype(int), level=2, inplace=True)
    df.sort_values(['cohort', 'day'], axis=1, inplace=True)
    
    col_index = df.columns.to_frame()
    col_index.reset_index(drop=True, inplace=True)
    col_index['month'] = np.floor(col_index['day']*12/365).astype(int)
    col_index = pd.merge(col_index, chortDf,
                         on='cohort',
                         how='left',
                         sort=False)
    col_index = col_index.drop(columns=['atsi', 'morbid'])
    df.columns = pd.MultiIndex.from_frame(col_index)
    
    df = df.groupby(level=[4, 3], axis=1).sum()
    
    # In the ABM age range 15 represents ages 10-17 while age range 25 is
    # ages 18-30. First redestribute these cohorts sothey align with 10 year
    # increments.
    df[15], df[25] = df[15] + df[25]/5, df[25]*4/5

    
    # Then split the 10 year cohorts in half.
    ageCols = [i*10 + 5 for i in range(10)]
    for age in ageCols:
        for j in range(12):
            # TODO, vectorise?
            df[age - 2.5, j] = df[age, j]/2
            df[age + 2.5, j] = df[age, j]/2
    
    # Add extra cohorts missing from ABM
    # Very few people are over 100
    for j in range(12):
        df[102.5, j] = 0
        df[107.5, j] = 0
    
    df = df.drop(columns=ageCols, level=0)
    df = df.stack(level=[0,1])
    Output('step1/infect_' + typeAppend, df)
    

def ProcessCohorts(filename, cohortFile, typeAppend):
    cohortData = GetCohortData(cohortFile)
    chunksize = 4 ** 7
    
    for chunk in tqdm(pd.read_csv(filename + '.csv', 
                             index_col=list(range(9)),
                             header=list(range(3)),
                             dtype={'day' : int, 'cohort' : int},
                             chunksize=chunksize),
                      total=4):
        ProcessChunk(chunk, cohortData, typeAppend)


############### Step 2 ###############

def CombineCsvColumns(path, output, nameList):
    df = None
    for n, value in tqdm(enumerate(nameList), total=len(nameList)):
        if n == 0:
            df = LoadColumn(path, str(value), 8)
            df.rename(columns={'value' : 'draw_1'}, inplace=True)
        else:
            df['draw_' + str(n + 1)] = LoadColumn(path, str(value), 8)['value']

    df['draw_0'] = df.mean(axis=1)
    
    index = df.index.to_frame()
    index['year_start'] = (index['month'])/12
    index['year_end']   = (index['month'] + 1)/12
    index['age_start']  = index['age'] - 2.5
    index['age_end']    = index['age'] + 2.5
    index = index.drop(columns=['age', 'month'])
    df.index = pd.MultiIndex.from_frame(index)
    
    df.to_csv(output + '.csv')


def CombineDraws(path):
    fileList = os.listdir(path)
    nameList = list(set(list(map(
        lambda x: int(x[re.search(r'\d', x).start():x.find('.')]), fileList))))
    nameList.sort()
    CombineCsvColumns('step1/infect_vac', 'step2/comb_infect_vac', nameList)
    CombineCsvColumns('step1/infect_noVac', 'step2/comb_infect_noVac', nameList)
  

############### Step 3 ###############      


def GetEffectsData(file):
    df = pd.read_csv(file + '.csv',
                header=[0])
    df = df.set_index(['vaccine', 'age_start', 'sex'])
    return df


def ProcessDrawTable(path, output, filename, multDf):
    df = pd.read_csv(path + '/' + filename + '.csv',
                header=[0],
                index_col=list(range(10)))
    
    enddf = df[df.index.isin([11.5/12], level=7)]
    enddf = enddf*0
    index = enddf.index.to_frame()
    index['year_start'] = index['year_end']
    index['year_end']   = 120
    enddf.index = pd.MultiIndex.from_frame(index)
    df = df.append(enddf)
    
    df = pd.concat([df, df], axis=1, keys=('male','female'))/2
    df.columns.set_names('sex', level=[0], inplace=True)
    df = df.stack(level=[0])
    
    df = df.mul(multDf, axis=0)
    df.index = df.index.reorder_levels(order=[
        'param_policy', 'param_vac_uptake', 'param_vac1_tran_reduct',
        'param_vac2_tran_reduct', 'param_trigger_loosen', 'R0', 'sex',
        'age_start', 'age_end', 'year_start', 'year_end'])
    
    #df.to_csv(output + '/' + filename + '.csv')
    return df
    

def ProcessEachDrawTable(path, output):
    cohortEffect = GetEffectsData('chort_effects')
    
    df_mort_vac   = ProcessDrawTable(path, output, 'comb_infect_vac', 
                                     cohortEffect.loc[1]['mort'])
    df_mort_noVac = ProcessDrawTable(path, output, 'comb_infect_noVac',
                                     cohortEffect.loc[0]['mort'])
    df_morb_vac   = ProcessDrawTable(path, output, 'comb_infect_vac',
                                     cohortEffect.loc[1]['morb'])
    df_morb_noVac = ProcessDrawTable(path, output, 'comb_infect_noVac',
                                     cohortEffect.loc[0]['morb'])
    
    (df_mort_vac + df_mort_noVac).to_csv(output + '/acute_disease.covid.mortality.csv')
    (df_morb_vac + df_morb_noVac).to_csv(output + '/acute_disease.covid.morbidity.csv')


############### Step 1 Stages ###############     

def ProcessChunkStage(df):
    df.columns.set_levels(df.columns.levels[1].astype(int), level=1, inplace=True)
    df.columns.set_levels(df.columns.levels[2].astype(int), level=2, inplace=True)
    
    df.columns = df.columns.droplevel([0, 2])
    
    col_index = df.columns.to_frame()
    col_index.reset_index(drop=True, inplace=True)
    col_index['month'] = np.floor(col_index['day']*12/365).astype(int)
    df.columns = pd.MultiIndex.from_frame(col_index)
    
    df = df.apply(lambda c: [1 if x > 2 else 0 for x in c])
    df = df.groupby(level=[1], axis=1).mean()
    
    df = df.stack(level=[0])
    Output('step1_stage/stage', df)


def ProcessStages(filename):
    chunksize = 4 ** 7
    
    for chunk in tqdm(pd.read_csv(filename + '.csv', 
                             index_col=list(range(9)),
                             header=list(range(3)),
                             dtype={'day' : int, 'cohort' : int},
                             chunksize=chunksize),
                      total=4):
        ProcessChunkStage(chunk)


############### Step 2 Stages ###############

def CombineCsvColumnsStage(path, output, nameList):
    df = None
    for n, value in tqdm(enumerate(nameList), total=len(nameList)):
        if n == 0:
            df = LoadColumn(path, str(value), 7)
            df.rename(columns={'value' : 'draw_1'}, inplace=True)
        else:
            df['draw_' + str(n + 1)] = LoadColumn(path, str(value), 7)['value']

    df['draw_0'] = df.mean(axis=1)
    
    index = df.index.to_frame()
    index = index[['param_policy', 'param_vac_uptake', 'param_vac1_tran_reduct',
                   'param_vac2_tran_reduct', 'param_trigger_loosen', 'R0', 'month']]
    index['year_start'] = (index['month'])/12
    index['year_end']   = (index['month'] + 1)/12
    index = index.drop(columns=['month'])
    df.index = pd.MultiIndex.from_frame(index)

    enddf = df[df.index.isin([11.5/12], level=7)]
    enddf = enddf*0
    index = enddf.index.to_frame()
    index['year_start'] = index['year_end']
    index['year_end']   = 120
    enddf.index = pd.MultiIndex.from_frame(index)
    df = df.append(enddf)
    
    df.to_csv(output + '.csv')


def CombineDrawsStage(path):
    fileList = os.listdir(path)
    nameList = list(set(list(map(
        lambda x: int(x[re.search(r'\d', x).start():x.find('.')]), fileList))))
    nameList.sort()
    CombineCsvColumnsStage('step1_stage/stage', 'step2_stage/lockdown_stage', nameList)


############### Run Infection Processing ###############

#ProcessCohorts('abm_out/processed_infectVac', 'abm_out/processed_static', 'vac')
#ProcessCohorts('abm_out/processed_infectNoVac', 'abm_out/processed_static', 'noVac')
CombineDraws('step1')
ProcessEachDrawTable('step2', 'step3')

#ProcessStages('abm_out/processed_stage')
CombineDrawsStage('step1_stage')