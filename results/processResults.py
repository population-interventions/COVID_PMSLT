# -*- coding: utf-8 -*-
"""
Created on Fri Mar 26 11:16:18 2021

@author: wilsonte
"""

import math
import pandas as pd
import numpy as np
from tqdm import tqdm

dataPrefix = 'covid4/data'

diseaseFiles = [
     'output_anxiety',  
     'output_covid_param',
     'output_depressive',
     #'output_falls',
     'output_roadinjury', 
     'output_selfharm',
]

forceNonPositive = {
     'output_anxiety' : True,  
     'output_covid_param' : True,
     'output_depressive' : True,
     'output_selfharm' : True,
     'output_roadinjury' : False,
}

runList = []
for a, policy in enumerate(['AggressElim', 'ModerateElim', 'TightSupress', 'LooseSupress']):
    for b, uptake in enumerate(['60', '75', '90']):
        for c, tran1 in enumerate(['50', '75', '90']):
            for d, tran2 in enumerate(['50', '75', '90']):
                for e, loose in enumerate(['FALSE', 'TRUE']):
                    for f, rep in enumerate(['2.5', '3.125', '3.75']):
                        run = 'covid_param_policy{0}_param_vac_uptake{1}_param_vac1_tran_reduct{2}_param_vac2_tran_reduct{3}_param_trigger_loosen{4}_R0{5}_'.format(
                            policy, uptake, tran1, tran2, loose, rep)
                        index = '{0}{1}{2}{3}{4}{5}'.format(a, b, c, d, e, f)
                        
                        runList.append({
                            'path' : '{0}_{1}/'.format(dataPrefix, index),
                            'params' : {
                                'param_policy'           : policy,
                                'param_vac1_tran_reduct' : tran1,
                                'param_vac2_tran_reduct' : tran2,
                                'param_vac_uptake'       : uptake,
                                'param_trigger_loosen'   : loose,
                                'R0'                     : rep,
                            },
                        })


def CalculateHalyExpect():
    df = pd.read_csv('covid2_000000/output_mm.csv',
                    header=[0])
    df = df[['sex', 'age', 'month', 'bau_population', 'bau_person_years',
             'bau_yld_rate',  'bau_acmr', 'bau_HALY']]
    df['age'] = np.ceil(df['age']) # Turn ages into age-cohort.
    df = df[df.month == 12]
    df = df.drop(columns=['month'])
    
    df['bau_HALY'] = df['bau_person_years'] * (1 - df['bau_yld_rate'] * 12)
    df.columns = ['sex','age', 'pop_0', 'personYear', 'yld', 'acmr', 'HALY_0']
    
    # Convert from monthly to yearly.
    df['yld'] = df['yld'] * 12
    df['HALY_0'] = df['HALY_0'] * 12
    
    df = df.set_index(['sex', 'age'])
    # TODO: Multiply acmr by 12
    #df.to_csv('test.csv')


def LoadLifeExpect():
    df = pd.read_csv('death_haly_loss.csv',
                    header=[0])
    df['age'] = (df['age'] - 1).astype(float)
    df = df.set_index(['sex', 'age'])
    return df


def ProcessRun(run, lifeExpect):
    df_main = pd.read_csv(run.get('path') + 'output_mm.csv',
                    header=[0])

    df_main = df_main[['sex', 'age', 'month', 'HALY', 'bau_HALY',
                       'person_years', 'bau_person_years', 'yld_rate', 'bau_yld_rate']]
    df_main['age'] = np.floor(df_main['age']) # Turn ages into age-cohort.
    df_main = df_main.set_index(['sex', 'age', 'month'])
    
    df_dis = pd.DataFrame()
    df_mort = pd.DataFrame()
    for fileName in diseaseFiles:
        df = pd.read_csv(run.get('path') + fileName + '.csv',
                    header=[0])
        df = df.set_index(['sex', 'age'])
        df.columns = ['year','month', 'bau_death', 'bau_HALY', 'death', 'HALY']
        df = df.drop(columns=['year'])
        df = df.reset_index()
        df['age'] = np.floor(df['age']) # Turn ages into age-cohort.
        df['month_2'] = df['month']
        df = df.set_index(['sex', 'age', 'month'])
        
        # Find the difference between intervention and BAU
        df['H_diff'] = df['HALY'] - df['bau_HALY']
        df['D_diff'] = df['death'] - df['bau_death']
        #print('fileNamefileNamefileName', fileName)
        #print(df['HALY'])
        #print(df['bau_HALY'])
        df = df.drop(columns=['bau_death', 'bau_HALY', 'death', 'HALY'])
        
        # Add death effects over the year.
        # Note that bau_yld_rate is actually rate per timestep, so per month
        df['D_effect'] = df['D_diff'] * (12.5 - df['month_2'])/12 * (1 - 12 * df_main['bau_yld_rate'])
        df = df.drop(columns=['month_2'])
        df['H_diff'] = df['H_diff'] - df['D_effect']
        
        df = df.groupby(level=[0, 1]).sum()
        # Zero Haly gain of numbers like 1.09E-05
        if forceNonPositive[fileName]:
            df['H_diff'] = df['H_diff'].combine(0, min)
        
        df_dis['morbidity', fileName[7:]] = df['H_diff']
        df_mort['mortality', fileName[7:]] = -df['D_diff'] * lifeExpect['HALY/Pop_0']
    
    # Sum HALYs for each cohort.
    halySum = df_dis.sum(axis=1)
    mainHalySum = (df_main['HALY'] - df_main['bau_HALY']).groupby(level=[0, 1]).sum()
    #print(halySum)
    #print(mainHalySum)
    #print(death_change['output_covid_param'])
    
    # Recale HALY diff so it matches main lifetable diff.
    df_dis = df_dis.mul(np.abs(mainHalySum / halySum).fillna(1), axis=0)
    #print((mainHalySum / halySum).fillna(1))
    
    #df_dis['morbidity', 'total'] = mainHalySum
    df_dis = df_dis.merge(df_mort, left_index=True, right_index=True)
    df_dis = df_dis.sum()
    
    df_dis = df_dis.append(pd.Series(run['params']))
    return df_dis
    

def DoProcess(runListIn):
    df = pd.DataFrame()
    lifeExpect = LoadLifeExpect()
    count = 0
    for run in tqdm(runListIn, total=648):
        #if count > 623:
        df = df.append(ProcessRun(run, lifeExpect), ignore_index=True)
        #count = count + 1
        #if count > 642:
        #    break
    
    df = df.set_index(['param_policy', 'param_vac1_tran_reduct', 'param_vac2_tran_reduct',
                       'param_vac_uptake', 'param_trigger_loosen', 'R0'])
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    df.to_csv('haly_output.csv')
    
DoProcess(runList)