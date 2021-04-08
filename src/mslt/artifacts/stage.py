"""Build a stage threhsold."""

import logging
import pandas as pd
import numpy as np
import pathlib


class Stages:

    def __init__(self, artifact, data_dir, year_start, year_end, write_table, num_draws):
        self._year_start = year_start
        self._year_end = year_end
        self.keep_cols = ['draw_' + str(i) for i in range(num_draws + 1)]
        self.data_dir = '{}/'.format(data_dir)
        self.artifact = artifact
        self.write_table = write_table
        self.load_stages_data('lockdown_stage')


    def RecursivelyOutputLevelFilter(self, df, suffix, levelsRemaining, prefix):
        if levelsRemaining >= 1:
            levelsRemaining -= 1
            levelName = df.index.levels[0].name
            for name, subDf in df.groupby(level=0):
            #for name in df.index.unique(level=0):
            #    subDf = df[df.index.isin([name], level=0)]
                subDf = df[df.index.isin([name], level=0)]
                subDf.index = subDf.index.droplevel(level=0)
                self.RecursivelyOutputLevelFilter(
                    subDf, suffix, levelsRemaining,
                    prefix + levelName + str(name).replace('.', '') + '_')
            return
        
        #df = df.stack().to_frame()
        #df = df.reset_index()
        #df = df.rename(columns={'level_2' : 'draw', 0 : 'value'})
        #df['draw'] = df['draw'].str.replace('draw_', '').astype(int)
        df = df.reset_index()
        self.write_table(self.artifact, 'stage.covid_' + prefix + '.' + suffix, df)


    def load_stages_data(self, dataPath):
        #logger = logging.getLogger(__name__)
        path = pathlib.Path(self.data_dir + dataPath + '.csv')
        df = pd.read_csv(path,
                        index_col=list(range(8)),
                        header=[0])
        indexDf = df.index.to_frame()
        indexDf['year_start'] = indexDf['year_start'] + self._year_start
        indexDf['year_end'] = indexDf['year_end'] + self._year_start
        df.index = pd.MultiIndex.from_frame(indexDf)

        df = df[df.columns[df.columns.isin(self.keep_cols)]]
        self.RecursivelyOutputLevelFilter(df, 'stage3and4', 6, '')
