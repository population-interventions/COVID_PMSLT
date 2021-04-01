"""
===================
Intervention Models
===================

This module contains tools for modeling interventions in multi-state lifetable
simulations.

"""

class LockdownAcuteDisease:
    """Interventions that modify an acute disease fatality rate."""

    def __init__(self, name):
        self._name = name
        
    @property
    def name(self):
        return self._name

    def setup(self, builder):
        self.config = builder.configuration
        diseaseMort = self.config['lockdown'].affects.mortality
        self.diseaseMortRates = {
            d : diseaseMort[d] for _,d in enumerate(diseaseMort)
        }
        diseaseDis = self.config['lockdown'].affects.morbidity
        self.diseaseDisRates = {
            d : diseaseDis[d] for _,d in enumerate(diseaseDis)
        }

        situation = self.config['acute_disease'].covid.data_name
        stage_data = builder.data.load('stage.' + situation + '.stage3and4')
        self.stage_table = builder.lookup.build_table(stage_data, 
                                               parameter_columns=['year'])
        #stage_table = builder.value.register_value_producer('stage_table', source=stage_table)
        
        for disease in self.diseaseMortRates:
            builder.value.register_value_modifier('{}_intervention.excess_mortality'.format(disease), 
                lambda index, rates: rates * (self.diseaseMortRates[disease] * self.stage_table(index)
                                             + (1 - self.stage_table(index))))
            builder.value.register_value_modifier('{}_intervention.yld_rate'.format(disease),
                lambda index, rates: rates * (self.diseaseDisRates[disease] * self.stage_table(index)
                                             + (1 - self.stage_table(index))))
