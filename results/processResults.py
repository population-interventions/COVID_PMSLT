# -*- coding: utf-8 -*-
"""
Created on Fri Mar 26 11:16:18 2021

@author: wilsonte
"""

import math
import pandas as pd
import numpy as np
from tqdm import tqdm

diseaseFiles = [
     'output_anxiety',  
     'output_covid_param',
     'output_depressive',
     'output_falls',
     'output_roadinjury', 
     'output_selfharm',
]

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
                            'path' : 'covid2_{0}/'.format(index),
                            'params' : {
                                'param_policy'           : policy,
                                'param_vac1_tran_reduct' : tran1,
                                'param_vac2_tran_reduct' : tran2,
                                'param_vac_uptake'       : uptake,
                                'param_trigger_loosen'   : loose,
                                'R0'                     : rep,
                            },
                        })


def ProcessRun(run):
    df_main = pd.read_csv(run.get('path') + 'output_mm.csv',
                    header=[0])
    
    df_main = df_main[['sex', 'age', 'month', 'HALY', 'bau_HALY', 'bau_yld_rate']]
    df_main['age'] = np.floor(df_main['age']) # Turn ages into age-cohort.
    df_main = df_main.set_index(['sex', 'age', 'month'])
        
    # Fix HALY factor here because I'm not rerunning the model.
    # TODO: Remove for fixed model.
    df_main['bau_HALY'] = df_main['bau_HALY'] * 12
    df_main['HALY'] = df_main['HALY'] * 12
    
    df_dis = pd.DataFrame()
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
        
        # Fix HALY factor here because I'm not rerunning the model.
        # TODO: Remove for fixed model.
        df['bau_HALY'] = df['bau_HALY'] * 12
        df['HALY'] = df['HALY'] * 12
        
        # Find the difference between intervention and BAU
        df['H_diff'] = df['HALY'] - df['bau_HALY']
        df['D_diff'] = df['death'] - df['bau_death']
        df = df.drop(columns=['bau_death', 'bau_HALY', 'death', 'HALY'])
        
        # Note that bau_yld_rate is actually per month at model output, so the code below
        # makes sense.
        df['D_diff'] = df['D_diff'] * (12.5 - df['month_2']) * (1 - df_main['bau_yld_rate'])
        df = df.drop(columns=['month_2'])
        
        df['H_diff'] = df['H_diff'] - df['D_diff']
        df_dis[fileName] = df['H_diff'].groupby(level=[0, 1]).sum()
    
    # Sum HALYs for each cohort.
    halySum = df_dis.sum(axis=1)
    mainHalySum = (df_main['HALY'] - df_main['bau_HALY']).groupby(level=[0, 1]).sum()
    
    # Recale HALY diff so they match main lifetable diff.
    df_dis = df_dis.mul(mainHalySum / halySum, axis=0)
    df_dis['total'] = mainHalySum
    df_dis = df_dis.sum()
    
    df_dis = df_dis.append(pd.Series(run['params']))
    return df_dis
    

def DoProcess(runListIn):
    df = pd.DataFrame()
    earlyEnd = 0
    for run in tqdm(runListIn, total=648):
        haly = ProcessRun(run)
        df = df.append(haly, ignore_index=True)
        earlyEnd = earlyEnd + 1
        if earlyEnd > 300:
            break
    
    df = df.set_index(['param_policy', 'param_vac1_tran_reduct', 'param_vac2_tran_reduct', 'param_vac_uptake', 'param_trigger_loosen', 'R0'])
    df.to_csv('haly_output.csv')
    
DoProcess(runList)