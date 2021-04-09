"""Build population data tables."""

import pandas as pd
import numpy as np
import pathlib

from .uncertainty import sample_fixed_rate_from
from .utilities import UnstackDraw


def ProcessDataTable(df, year_start, max_age):
    # Retain only the necessary columns.
    df['year'] = year_start
    #convert age to float for non-year timesteps
    df['age'] = df['age'].astype(float)
    # Remove strata that have already reached the terminal age.
    df = df[~ (df.age == max_age)]
    # Sort the rows.
    df = df.sort_values(by=['year', 'age', 'sex']).reset_index(drop=True)
    return df


class Population:

    def __init__(self, data_dir, year_start):
        df_pop = pd.read_csv(str(pathlib.Path('{}/base_population.csv'.format(data_dir)).resolve()))


        df_life = pd.read_csv(str(pathlib.Path('{}/base_lifetable.csv'.format(data_dir)).resolve()))
        df_life = df_life.rename(columns={'mortality per 1 rate': 'mortality_rate',
                                'pYLD rate': 'disability_rate',
                                'APC in all-cause mortality': 'mortality_apc'})
        
        # Retain only the necessary columns.
        df_life = df_life[['age', 'sex', 'disability_rate', 'mortality_rate', 'mortality_apc']]

        # Add years and sort rows.
        df_pop = ProcessDataTable(df_pop, year_start, df_life['age'].max())
        df_life = ProcessDataTable(df_life, year_start, df_life['age'].max())

        self.year_start = year_start
        self.year_end = year_start + df_pop['age'].max() - df_pop['age'].min()
        self._num_apc_years = 15

        self._df_pop = df_pop
        self._df_life = df_life

    def years(self):
        """Return an iterator over the simulation period."""
        return range(int(self.year_start), int(self.year_end + 1))

    def get_population(self):
        """Return the initial population size for each stratum."""
        # Retain only those strata for whom the population size is defined.
        df = self._df_pop.rename(columns = {'population': 'value'})
        return df

    def sample_disability_rate_from(self, rate_dist, samples):
        """
        Sample values for the disability rate for each stratum.

        :param rate_dist: The sampling distribution.
        :param samples: Random samples from the half-open interval [0, 1).
        """
        df = self._df_life.rename(columns={'disability_rate': 'rate'})
        df = sample_fixed_rate_from(self.year_start, self.year_end,
                                    df, 'rate',
                                    rate_dist, samples)                          
        df = df.rename(columns = {'rate': 'value'})

        df = UnstackDraw(df)

        return df

    def get_disability_rate(self):
        """Return the disability rate for each stratum."""
        df = self._df_life[['age', 'sex', 'disability_rate']]
        df = df.rename(columns={'disability_rate': 'value'})

        #convert age to float for non-year timesteps
        df['age'] = df['age'].astype(float)

        # Replace 'age' with age groups.
        df = df.rename(columns={'age': 'age_start'})
        df.insert(df.columns.get_loc('age_start') + 1,
                  'age_end',
                  df['age_start'] + 1)

        # These values apply at each year of the simulation, so we only need
        # to define a single bin.
        df.insert(0, 'year_start', self.year_start)
        df.insert(1, 'year_end', self.year_end + 1)

        df = df.sort_values(['year_start', 'age_start', 'sex'])
        df = df.reset_index(drop=True)

        return df

    def get_acmr_apc(self):
        """Return the annual percent change (APC) in mortality rate."""
        df = self._df_life[['year', 'age', 'sex', 'mortality_apc']]
        df = df.rename(columns={'mortality_apc': 'value'})

        tables = []
        for year in self.years():
            df['year'] = year
            tables.append(df.copy())

        #convert age to float for non-year timesteps
        df['age'] = df['age'].astype(float)

        df = pd.concat(tables).sort_values(['year', 'age', 'sex'])
        df = df.reset_index(drop=True)

        return df

    def get_mortality_rate(self):
        """
        Return the mortality rate for each strata.

        :param df_base: The base population data.
        """
        # NOTE: see column IG in ErsatzInput.
        # - Each cohort has a separate APC (column FE)
        # - ACMR = BASE_ACMR * e^(APC * (year - 2011))
        df_apc = self.get_acmr_apc()
        df_acmr = self._df_life[['age', 'sex', 'mortality_rate']]
        df_acmr = df_acmr.rename(columns={'mortality_rate': 'value'})
        base_acmr = df_acmr['value'].copy()

        #convert age to float for non-year timesteps
        df_acmr['age'] = df_acmr['age'].astype(float)
        # Replace 'age' with age groups.
        df_acmr = df_acmr.rename(columns={'age': 'age_start'})
        df_acmr.insert(df_acmr.columns.get_loc('age_start') + 1,
                       'age_end',
                       df_acmr['age_start'] + 1)

        # These values apply at each year of the simulation, so we only need
        # to define a single bin.
        df_acmr.insert(0, 'year_start', self.year_start -1)
        df_acmr.insert(1, 'year_end', self.year_start)

        tables = []
        tables.append(df_acmr.copy())
        for counter, year in enumerate(self.years()):
            if counter <= self._num_apc_years:
                year_apc = df_apc[df_apc.year == year]
                apc = year_apc['value'].values
                scale = np.exp(apc * (year - self.year_start))
                df_acmr.loc[:, 'value'] = base_acmr * scale
            else:
                # NOTE: use the same scale for this cohort as per the previous
                # year; shift by 2 because there are male and female cohorts.
                scale[2:] = scale[:-2]
                df_acmr.loc[:, 'value'] = base_acmr * scale
            df_acmr['year_start'] = year
            df_acmr['year_end'] = year + 1
            tables.append(df_acmr.copy())

        df = pd.concat(tables).sort_values(['year_start', 'age_start',
                                            'sex'])
        df = df.reset_index(drop=True)

        return df
