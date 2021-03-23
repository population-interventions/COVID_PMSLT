"""Build covid in a unique way."""

import logging
import pandas as pd
import numpy as np
import pathlib


class Covid:

    def __init__(self, artifact, data_dir, year_start, year_end, pop, write_table, num_draws):
        self._year_start = year_start
        self._year_end = year_end
        self.keep_cols = ['draw_' + str(i) for i in range(num_draws + 1)]
        self.data_dir = '{}/covid/'.format(data_dir)
        self.artifact = artifact
        self.pop = pop
        self.write_table = write_table
        self.load_diseases_data('mortality')
        self.load_diseases_data('morbidity')
        self.load_diseases_data('expenditure')


    def RecursivelyOutputLevelFilter(self, df, suffix, levelsRemaining, prefix):
        if levelsRemaining >= 1:
            levelsRemaining -= 1
            levelName = df.index.levels[0].name
            for name in df.index.unique(level=0):
                subDf = df[df.index.isin([name], level=0)]
                subDf.index = subDf.index.droplevel(level=0)
                self.RecursivelyOutputLevelFilter(
                    subDf, suffix, levelsRemaining,
                    prefix + levelName + str(name).replace('.', '') + '_')
            return
        
        df = df[df.columns[df.columns.isin(self.keep_cols)]]
        df = df.reset_index()
        self.write_table(self.artifact, 'acute_disease.covid_' + prefix + '.' + suffix, df)


    def load_diseases_data(self, suffix):
        #logger = logging.getLogger(__name__)
        path = pathlib.Path(self.data_dir + 'acute_disease.covid.' + suffix + '.csv')
        df = pd.read_csv(path,
                        index_col=list(range(11)),
                        header=[0])
        indexDf = df.index.to_frame()
        indexDf['year_start'] = indexDf['year_start'] + self._year_start
        indexDf['year_end'] = indexDf['year_end'] + self._year_start
        df.index = pd.MultiIndex.from_frame(indexDf)

        popDf = self.pop
        popDf['age_start'] = popDf['age'] - 2
        popDf['age_end'] = popDf['age'] + 3
        popDf = popDf.set_index(['sex', 'age_start', 'age_end'])

        # Convert raw infections to a proportion of the population
        df = df.div(popDf['value'], axis=0).reorder_levels(df.index.names)

        # Convert from infections per month to per year. Vivarium wants everything
        # in per year and scales down for shorter timesteps.
        df = df * 12

        self.RecursivelyOutputLevelFilter(df, suffix, 6, '')
