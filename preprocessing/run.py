
import math
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import os

fileCreated = {}

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


def GetEffectsData(cohortFile):
    df = pd.read_csv(cohortFile + '.csv',
                header=[0])
    df = df.set_index('age')
    return df


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


def Output(name, path, df, cohortEffect):
    df = df.transpose()
    df = df.mul(cohortEffect[name], axis=0)
    df = df.transpose()
    
    df = df.stack(level=[0,1])
    index = df.index.to_frame(index=False)
    index = index.drop(columns=['run', 'global_transmissibility'])
    df.index = pd.MultiIndex.from_frame(index)
    df = df.rename('value')
    
    for value in index.rand_seed.unique():
        rdf = df[df.index.isin([value], level=0)]
        rdf = rdf.reset_index()
        rdf = rdf.drop(columns='rand_seed')
        OutputToFile(rdf, path, value)


def ProcessChunk(df, chortDf, cohortEffect):
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
    
    df = df.drop(columns=ageCols, level=0)
    cohortEffect = cohortEffect.reindex(df.transpose().index, level=0)
    Output('mort', 'step1/mort', df, cohortEffect)
    Output('morb', 'step1/morb', df, cohortEffect)
    Output('cost', 'step1/cost', df, cohortEffect)
    

def Process(filename, cohortFile):
    cohortData = GetCohortData(cohortFile)
    cohortEffect = GetEffectsData('chort_effects')
    chunksize = 4 ** 7
    
    for chunk in tqdm(pd.read_csv(filename + '.csv', 
                             index_col=list(range(9)),
                             header=list(range(3)),
                             dtype={'day' : int, 'cohort' : int},
                             chunksize=chunksize),
                      total=4):
        ProcessChunk(chunk, cohortData, cohortEffect)


############### Step 2 ###############

def LoadColumn(path, inName, output):
    return pd.read_csv(path + '_' + inName + '.csv',
                header=[0],
                index_col=list(range(8)))
   

def CombineCsvColumns(path, output, nameList):
    df = None
    for n, value in tqdm(enumerate(nameList), total=len(nameList)):
        if n == 0:
            df = LoadColumn(path, str(value), output)
            df.rename(columns={'value' : 'draw_0'}, inplace=True)
        else:
            df['draw_' + str(n)] = LoadColumn(path, str(value), output)['value']

    index = df.index.to_frame()
    index['year_start'] = (index['month'] - 0.5)/12
    index['year_end']   = (index['month'] + 0.5)/12
    index['age_start']  = index['age'] - 2.5
    index['age_end']    = index['age'] + 2.5
    index = index.drop(columns=['age', 'month'])
    df.index = pd.MultiIndex.from_frame(index)
    
    df.to_csv(output + '.csv')


def CombineDraws(path):
    fileList = os.listdir(path)
    nameList = list(set(list(map(
        lambda x: int(x[(x.find('_') + 1):x.find('.')]), fileList))))
    nameList.sort()
    CombineCsvColumns('step1/mort', 'step2/acute_disease.covid.mortality', nameList)
    CombineCsvColumns('step1/morb', 'step2/acute_disease.covid.morbidity', nameList)
    CombineCsvColumns('step1/cost', 'step2/acute_disease.covid.expenditure', nameList)
  

############### Step 3 ###############      

def ProcessDrawTable(path, output, filename):
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
    
    df.to_csv(output + '/' + filename + '.csv')
    

def ProcessEachDrawTable(path, output):
    ProcessDrawTable(path, output, 'acute_disease.covid.mortality')
    ProcessDrawTable(path, output, 'acute_disease.covid.morbidity')
    ProcessDrawTable(path, output, 'acute_disease.covid.expenditure')

#Process('abm_out/processed_infect_unique', 'abm_out/processed_static')
#CombineDraws('step1')
ProcessEachDrawTable('step2', 'step3')