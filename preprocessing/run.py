
import math
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import os

fileCreated = {}

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
    fullFilePath = path + '_' + str(fileAppend) + '.csv'
    if fileCreated.get(fileAppend):
        # Append
        df.to_csv(fullFilePath, mode='a', index=False, header=False)
    else:
        fileCreated[fileAppend] = True
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


def LoadAndAppendDraw(path, inName, outName, output):
    df = pd.read_csv(path + '_' + inName + '.csv',
                header=[0])
    print(df)
    


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
                      total=16):
        ProcessChunk(chunk, cohortData, cohortEffect)
    

def CombineDraws(path):
    fileList = os.listdir(path)
    nameList = list(set(list(map(
        lambda x: int(x[(x.find('_') + 1):x.find('.')]), fileList))))
    nameList.sort()
    for index, value in enumerate(nameList):
        LoadAndAppendDraw('step1/mort', str(value), str(index), 'step2/acute_disease.covid.mortality')
        LoadAndAppendDraw('step1/morb', str(value), str(index), 'step2/acute_disease.covid.morbidity')
        LoadAndAppendDraw('step1/cost', str(value), str(index), 'step2/acute_disease.covid.expenditure')
        
        

#Process('abm_out/processed_infect_unique', 'abm_out/processed_static')
CombineDraws('step1')