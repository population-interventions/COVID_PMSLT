"""
=================
Magic Wand Models
=================

This module contains tools for making crude adjustments to rates in
multi-state lifetable simulations.

"""


class MortalityShift:
    
    @property
    def name(self):
        return 'mortality_shift'

    def setup(self, builder):
        builder.value.register_value_modifier('mortality_rate', self.mortality_adjustment)

    def mortality_adjustment(self, index, rates):
        return rates * .5


class YLDShift:
    
    @property
    def name(self):
        return 'yld_shift'

    def setup(self, builder):
        builder.value.register_value_modifier('yld_rate', self.disability_adjustment)

    def disability_adjustment(self, index, rates):
        return rates * .5


class IncidenceShift:

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    def setup(self, builder):
        builder.value.register_value_modifier(f'{self.name}.incidence', self.incidence_adjustment)

        self.rate_mult = 0.5
        """Configuration."""
        if 'magic_wand' in builder.configuration and self.name in builder.configuration.magic_wand:
            configuration = builder.configuration.magic_wand[self.name]
            if configuration.rate_reduce:
                self.rate_mult = (1 - configuration.rate_reduce)

    def incidence_adjustment(self, index, rates):
        return rates * self.rate_mult


class ModifyAcuteDiseaseYLD:

    def __init__(self, name):
        self._name = name
        
    @property
    def name(self):
        return self._name

    def setup(self, builder):
        self.config = builder.configuration
        self.scale = self.config.intervention[self.name].yld_scale
        if self.scale < 0:
            raise ValueError(f'Invalid YLD scale: {self.scale}')
        builder.value.register_value_modifier(
            f'{self.name}_intervention.yld_rate',
            self.disability_adjustment)

    def disability_adjustment(self, index, rates):
        return rates * self.scale


class ModifyAcuteDiseaseMortality:

    def __init__(self, name):
        self._name = name
    
    @property
    def name(self):
        return self._name

    def setup(self, builder):
        self.config = builder.configuration
        self.scale = self.config.intervention[self.name].mortality_scale
        if self.scale < 0:
            raise ValueError(f'Invalid mortality scale: {self.scale}')
        builder.value.register_value_modifier(
            f'{self.name}_intervention.excess_mortality',
            self.mortality_adjustment)

    def mortality_adjustment(self, index, rates):
        return rates * self.scale
