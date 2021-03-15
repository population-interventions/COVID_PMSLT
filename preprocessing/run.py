
import math
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import os


def GetCohortData(cohortFile):
    df = pd.read_csv(cohortFile + '.csv', 
                index_col=[0],
                header=[0])
    df.index.rename('cohort', True)
    df = df.reset_index()
    df['cohort'] = df['cohort'].astype(int)
    df['age'] = df['age'].astype(int)
    return df


def GetMorbMortData(cohortFile):
    df = pd.read_csv(cohortFile + '.csv',
                header=[0])
    print(df)
    return df


def ProcessChunk(df, chortDf):
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
    print(df.head(10))
    

def Process(filename, cohortFile):
    cohortData = GetCohortData(cohortFile)
    morbMort = GetMorbMortData('morbmort')
    chunksize = 4 ** 4
    
    for chunk in pd.read_csv(filename + '.csv', 
                             index_col=list(range(9)),
                             header=list(range(3)),
                             dtype={'day' : int, 'cohort' : int},
                             chunksize=chunksize):
        ProcessChunk(chunk, cohortData)
        return
    

Process('abm_out/processed_infect_unique', 'abm_out/processed_static')