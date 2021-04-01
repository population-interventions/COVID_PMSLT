"""
==============
Disease Models
==============

This module contains tools for modeling diseases in multi-state lifetable
simulations.

"""
import numpy as np
import pandas as pd


class AcuteDisease:
    """
    An acute disease has a sufficiently short duration, relative to the
    time-step size, that it is not meaningful to talk about prevalence.
    Instead, it simply contributes an excess mortality rate, and/or a
    disability rate.

    Interventions may affect these rates:

    - `<disease>_intervention.excess_mortality`
    - `<disease>_intervention.yld_rate`

    where `<disease>` is the name as provided to the constructor.

    Parameters
    ----------
    name
        The disease name (referred to as `<disease>` here).

    """

    def __init__(self, name):
        self._name = name
        
    @property
    def name(self):
        return self._name

    def setup(self, builder):
        self.data_name = self.name
        self.no_bau = False
        
        """Configuration."""
        if 'acute_disease' in builder.configuration and self.name in builder.configuration.acute_disease:
            configuration = builder.configuration.acute_disease[self.name]
            if configuration.data_name:
                self.data_name = configuration.data_name
            if configuration.no_bau:
                self.no_bau = configuration.no_bau
                
        """Load the morbidity and mortality data."""
        mty_data = builder.data.load(f'acute_disease.{self.data_name}.mortality')
        mty_rate = builder.lookup.build_table(mty_data, 
                                              key_columns=['sex'], 
                                              parameter_columns=['age','year'])
        yld_data = builder.data.load(f'acute_disease.{self.data_name}.morbidity')
        yld_rate = builder.lookup.build_table(yld_data,
                                              key_columns=['sex'], 
                                              parameter_columns=['age','year'])
        self.excess_mortality = builder.value.register_rate_producer(
            f'{self.name}.excess_mortality',
            source=mty_rate)
        self.int_excess_mortality = builder.value.register_rate_producer(
            f'{self.name}_intervention.excess_mortality',
            source=mty_rate)
        self.disability_rate = builder.value.register_rate_producer(
            f'{self.name}.yld_rate',
            source=yld_rate)
        self.int_disability_rate = builder.value.register_rate_producer(
            f'{self.name}_intervention.yld_rate',
            source=yld_rate)
        builder.value.register_value_modifier('mortality_rate', self.mortality_adjustment)
        builder.value.register_value_modifier('yld_rate', self.disability_adjustment)

        self.years_per_timestep = builder.configuration.time.step_size/365
        columns = [
            self.name + '_deaths_bau', self.name + '_HALY_bau', 
            self.name + '_deaths', self.name + '_HALY'
        ]
        builder.population.initializes_simulants(
            self.on_initialize_simulants,
            creates_columns=columns,
            requires_columns=['age', 'sex'])
        self.population_view = builder.population.get_view([
            self.name + '_deaths_bau', self.name + '_HALY_bau', 
            self.name + '_deaths', self.name + '_HALY', 
            'population', 'person_years', 'bau_population', 'bau_person_years'])

    def on_initialize_simulants(self, pop_data):
        pop = pd.DataFrame({
                f'{self.name}_deaths_bau': 0.0,
                f'{self.name}_HALY_bau': 0.0,
                f'{self.name}_deaths': 0.0,
                f'{self.name}_HALY': 0.0,
            },
            index=pop_data.index)

        self.population_view.update(pop)


    def mortality_adjustment(self, index, mortality_rate):
        """
        Adjust the all-cause mortality rate in the intervention scenario, to
        account for any change in prevalence (relative to the BAU scenario).
        """
        pop = self.population_view.get(index)
        # self.years_per_timestep converts from per-year to per-month
        if self.no_bau:
            delta = self.int_excess_mortality(index)
            pop[self.name + '_deaths'] = pop.population * self.int_excess_mortality(index) * self.years_per_timestep
        else:
            delta = self.int_excess_mortality(index) - self.excess_mortality(index)
            pop[self.name + '_deaths'] = pop.population * self.int_excess_mortality(index) * self.years_per_timestep
            pop[self.name + '_deaths_bau'] = pop.bau_population * self.excess_mortality(index) * self.years_per_timestep
        
        self.population_view.update(pop)
        return mortality_rate + delta

    def disability_adjustment(self, index, yld_rate):
        """
        Adjust the years lost due to disability (YLD) rate in the intervention
        scenario, to account for any change in prevalence (relative to the BAU
        scenario).
        """
        pop = self.population_view.get(index)
        # person_years is already for this month, so no multiplier is required.
        if self.no_bau:
            delta = self.int_disability_rate(index)
            pop[self.name + '_HALY'] = -pop.person_years * self.int_disability_rate(index)
        else:
            delta = self.int_disability_rate(index) - self.disability_rate(index)
            pop[self.name + '_HALY'] = -pop.person_years * self.int_disability_rate(index)
            pop[self.name + '_HALY_bau'] = -pop.bau_person_years * self.disability_rate(index)
        
        self.population_view.update(pop)
        return yld_rate + delta


class Disease:
    """This component characterises a chronic disease.

    It defines the following rates, which may be affected by interventions:

    - `<disease>_intervention.incidence`
    - `<disease>_intervention.remission`
    - `<disease>_intervention.mortality`
    - `<disease>_intervention.morbidity`

    where `<disease>` is the name as provided to the constructor.

    Parameters
    ----------
    name
        The disease name (referred to as `<disease>` here).

    """

    def __init__(self, name):
        self._name = name
        self.configuration_defaults = {
            self.name: {
                'simplified_no_remission_equations': False,
            },
        }
        
    @property
    def name(self):
        return self._name

    def setup(self, builder):
        """Load the disease prevalence and rates data."""
        data_prefix = 'chronic_disease.{}.'.format(self.name)
        bau_prefix = self.name + '.'
        int_prefix = self.name + '_intervention.'

        self.clock = builder.time.clock()
        self.start_year = builder.configuration.time.start.year
        self.simplified_equations = builder.configuration[self.name].simplified_no_remission_equations

        inc_data = builder.data.load(data_prefix + 'incidence')
        i = builder.lookup.build_table(inc_data, 
                                       key_columns=['sex'], 
                                       parameter_columns=['age','year'])
        self.incidence = builder.value.register_rate_producer(
            bau_prefix + 'incidence', source=i)
        self.incidence_intervention = builder.value.register_rate_producer(
            int_prefix + 'incidence', source=i)

        rem_data = builder.data.load(data_prefix + 'remission')
        r = builder.lookup.build_table(rem_data, 
                                       key_columns=['sex'], 
                                       parameter_columns=['age','year'])
        self.remission = builder.value.register_rate_producer(
            bau_prefix + 'remission', source=r)

        mty_data = builder.data.load(data_prefix + 'mortality')
        f = builder.lookup.build_table(mty_data, 
                                       key_columns=['sex'], 
                                       parameter_columns=['age','year'])
        self.excess_mortality = builder.value.register_rate_producer(
            bau_prefix + 'excess_mortality', source=f)

        yld_data = builder.data.load(data_prefix + 'morbidity')
        yld_rate = builder.lookup.build_table(yld_data, 
                                              key_columns=['sex'], 
                                              parameter_columns=['age','year'])
        self.disability_rate = builder.value.register_rate_producer(
            bau_prefix + 'yld_rate', source=yld_rate)

        prev_data = builder.data.load(data_prefix + 'prevalence')
        self.initial_prevalence = builder.lookup.build_table(prev_data, 
                                                             key_columns=['sex'], 
                                                             parameter_columns=['age','year'])

        builder.value.register_value_modifier(
            'mortality_rate', self.mortality_adjustment)
        builder.value.register_value_modifier(
            'yld_rate', self.disability_adjustment)

        columns = []
        for scenario in ['', '_intervention']:
            for rate in ['_S', '_C']:
                for when in ['', '_previous']:
                    columns.append(self.name + rate + scenario + when)

        builder.population.initializes_simulants(
            self.on_initialize_simulants,
            creates_columns=columns,
            requires_columns=['age', 'sex'])
        self.population_view = builder.population.get_view(columns)

        builder.event.register_listener(
            'time_step__prepare',
            self.on_time_step_prepare)

    def on_initialize_simulants(self, pop_data):
        """Initialize the test population for which this disease is modeled."""
        C = 1000 * self.initial_prevalence(pop_data.index)
        S = 1000 - C

        pop = pd.DataFrame({f'{self.name}_S': S,
                            f'{self.name}_C': C,
                            f'{self.name}_S_previous': S,
                            f'{self.name}_C_previous': C,
                            f'{self.name}_S_intervention': S,
                            f'{self.name}_C_intervention': C,
                            f'{self.name}_S_intervention_previous': S,
                            f'{self.name}_C_intervention_previous': C},
                           index=pop_data.index)

        self.population_view.update(pop)

    def on_time_step_prepare(self, event):
        """
        Update the disease status for both the BAU and intervention scenarios.
        """
        # Do not update the disease status in the first year, the initial data
        # describe the disease state at the end of the year.
        if self.clock().year == self.start_year:
            return
        pop = self.population_view.get(event.index)
        if pop.empty:
            return
        idx = pop.index
        S_bau, C_bau = pop[f'{self.name}_S'], pop[f'{self.name}_C']
        S_int = pop[f'{self.name}_S_intervention']
        C_int = pop[f'{self.name}_C_intervention']

        # Extract all of the required rates *once only*.
        i_bau = self.incidence(idx)
        i_int = self.incidence_intervention(idx)
        r = self.remission(idx)
        f = self.excess_mortality(idx)

        # NOTE: if the remission rate is always zero, which is the case for a
        # number of chronic diseases, we can make some simplifications.
        if np.all(r == 0):
            r = 0
            if self.simplified_equations:
                # NOTE: for the 'mslt_reduce_chd' experiment, this results in a
                # slightly lower HALY gain than that obtained when using the
                # full equations (below).
                new_S_bau = S_bau * np.exp(- i_bau)
                new_S_int = S_int * np.exp(- i_int)
                new_C_bau = C_bau * np.exp(- f) + S_bau - new_S_bau
                new_C_int = C_int * np.exp(- f) + S_int - new_S_int
                pop_update = pd.DataFrame({
                    f'{self.name}_S': new_S_bau,
                    f'{self.name}_C': new_C_bau,
                    f'{self.name}_S_previous': S_bau,
                    f'{self.name}_C_previous': C_bau,
                    f'{self.name}_S_intervention': new_S_int,
                    f'{self.name}_C_intervention': new_C_int,
                    f'{self.name}_S_intervention_previous': S_int,
                    f'{self.name}_C_intervention_previous': C_int,
                }, index=pop.index)
                self.population_view.update(pop_update)
                return

        # Calculate common factors.
        i_bau2 = i_bau**2
        i_int2 = i_int**2
        r2 = r**2
        f2 = f**2
        f_r = f * r
        i_bau_r = i_bau * r
        i_int_r = i_int * r
        i_bau_f = i_bau * f
        i_int_f = i_int * f
        f_plus_r = f + r

        # Calculate convenience terms.
        l_bau = i_bau + f_plus_r
        l_int = i_int + f_plus_r
        q_bau = np.sqrt(i_bau2 + r2 + f2 + 2 * i_bau_r + 2 * f_r - 2 * i_bau_f)
        q_int = np.sqrt(i_int2 + r2 + f2 + 2 * i_int_r + 2 * f_r - 2 * i_int_f)
        w_bau = np.exp(-(l_bau + q_bau) / 2)
        w_int = np.exp(-(l_int + q_int) / 2)
        v_bau = np.exp(-(l_bau - q_bau) / 2)
        v_int = np.exp(-(l_int - q_int) / 2)

        # Identify where the denominators are non-zero.
        nz_bau = q_bau != 0
        nz_int = q_int != 0
        denom_bau = 2 * q_bau
        denom_int = 2 * q_int

        new_S_bau = S_bau.copy()
        new_C_bau = C_bau.copy()
        new_S_int = S_int.copy()
        new_C_int = C_int.copy()

        # Calculate new_S_bau, new_C_bau, new_S_int, new_C_int.
        num_S_bau = (2 * (v_bau - w_bau) * (S_bau * f_plus_r + C_bau * r)
                     + S_bau * (v_bau * (q_bau - l_bau)
                                + w_bau * (q_bau + l_bau)))
        num_S_int = (2 * (v_int - w_int) * (S_int * f_plus_r + C_int * r)
                     + S_int * (v_int * (q_int - l_int)
                                + w_int * (q_int + l_int)))
        new_S_bau[nz_bau] = num_S_bau[nz_bau] / denom_bau[nz_bau]
        new_S_int[nz_int] = num_S_int[nz_int] / denom_int[nz_int]

        num_C_bau = - ((v_bau - w_bau) * (2 * (f_plus_r * (S_bau + C_bau)
                                               - l_bau * S_bau)
                                          - l_bau * C_bau)
                       - (v_bau + w_bau) * q_bau * C_bau)
        num_C_int = - ((v_int - w_int) * (2 * (f_plus_r * (S_int + C_int)
                                               - l_int * S_int)
                                          - l_int * C_int)
                       - (v_int + w_int) * q_int * C_int)
        new_C_bau[nz_bau] = num_C_bau[nz_bau] / denom_bau[nz_bau]
        new_C_int[nz_int] = num_C_int[nz_int] / denom_int[nz_int]

        pop_update = pd.DataFrame({
            f'{self.name}_S': new_S_bau,
            f'{self.name}_C': new_C_bau,
            f'{self.name}_S_previous': S_bau,
            f'{self.name}_C_previous': C_bau,
            f'{self.name}_S_intervention': new_S_int,
            f'{self.name}_C_intervention': new_C_int,
            f'{self.name}_S_intervention_previous': S_int,
            f'{self.name}_C_intervention_previous': C_int,
        }, index=pop.index)
        self.population_view.update(pop_update)

    def mortality_adjustment(self, index, mortality_rate):
        """
        Adjust the all-cause mortality rate in the intervention scenario, to
        account for any change in disease prevalence (relative to the BAU
        scenario).
        """
        pop = self.population_view.get(index)

        S, C = pop[f'{self.name}_S'], pop[f'{self.name}_C']
        S_prev, C_prev = pop[f'{self.name}_S_previous'], pop[f'{self.name}_C_previous']
        D, D_prev = 1000 - S - C, 1000 - S_prev - C_prev

        S_int, C_int = pop[f'{self.name}_S_intervention'], pop[f'{self.name}_C_intervention']
        S_int_prev, C_int_prev = pop[f'{self.name}_S_intervention_previous'], pop[f'{self.name}_C_intervention_previous']
        D_int, D_int_prev = 1000 - S_int - C_int, 1000 - S_int_prev - C_int_prev

        # NOTE: as per the spreadsheet, the denominator is from the same point
        # in time as the term being subtracted in the numerator.
        mortality_risk = (D - D_prev) / (S_prev + C_prev)
        mortality_risk_int = (D_int - D_int_prev) / (S_int_prev + C_int_prev)

        delta = np.log((1 - mortality_risk) / (1 - mortality_risk_int))

        return mortality_rate + delta

    def disability_adjustment(self, index, yld_rate):
        """
        Adjust the years lost due to disability (YLD) rate in the intervention
        scenario, to account for any change in disease prevalence (relative to
        the BAU scenario).
        """
        pop = self.population_view.get(index)

        S, S_prev = pop[f'{self.name}_S'], pop[f'{self.name}_S_previous']
        C, C_prev = pop[f'{self.name}_C'], pop[f'{self.name}_C_previous']
        S_int, S_int_prev = pop[f'{self.name}_S_intervention'], pop[f'{self.name}_S_intervention_previous']
        C_int, C_int_prev = pop[f'{self.name}_C_intervention'], pop[f'{self.name}_C_intervention_previous']

        # The prevalence rate is the mean number of diseased people over the
        # year, divided by the mean number of alive people over the year.
        # The 0.5 multipliers in the numerator and denominator therefore cancel
        # each other out, and can be removed.
        prevalence_rate = (C + C_prev) / (S + C + S_prev + C_prev)
        prevalence_rate_int = (C_int + C_int_prev) / (S_int + C_int + S_int_prev + C_int_prev)

        delta = prevalence_rate_int - prevalence_rate
        return yld_rate + self.disability_rate(index) * delta
