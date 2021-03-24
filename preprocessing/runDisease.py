
import math
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import os
import re

############### Output ###############

def OutputDisease(name, df):
    df = df.set_index(['age', 'sex'])
    df = df.reset_index()
    crossDf = pd.DataFrame({'extra' : range(5), 'cross_key' : 1})
    df['cross_key'] = 1
    df = df.merge(crossDf, how='outer', on='cross_key').drop('cross_key', axis=1)
    df['age'] = df['age'] + df['extra']
    df = df.drop('extra', axis=1)
    
    print(name)
    
    endRow = df[(df['age'] == 99) & (df['sex'] == 'male')]
    df = df.append(pd.DataFrame({
        'age' : [100 + i for i in range(11)],
        'sex' : 'male',
        'excess_mortality' : endRow.excess_mortality.iloc[0],
        'disability_rate' : endRow.disability_rate.iloc[0]
    }))
    endRow = df[(df['age'] == 99) & (df['sex'] == 'female')]
    df = df.append(pd.DataFrame({
        'age' : [100 + i for i in range(11)],
        'sex' : 'female',
        'excess_mortality' : endRow.excess_mortality.iloc[0],
        'disability_rate' : endRow.disability_rate.iloc[0]
    }))
    df.to_csv('disease_ready/' + name + '_rates.csv', index=False) 

def ProcessDiseaseTable(filename):
    df = pd.read_csv(filename + '.csv',
                header=[0],
                index_col=list(range(3)))
    
    for name, subDf in df.groupby(level=0):
        subDf = subDf.reset_index()
        subDf = subDf.drop(columns='name')
        OutputDisease(name, subDf)
    
    
############### Run ###############

ProcessDiseaseTable('disease/meanData')