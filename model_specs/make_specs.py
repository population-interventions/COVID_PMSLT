# -*- coding: utf-8 -*-
"""
Created on Thu Mar 25 16:19:40 2021

@author: wilsonte
"""

specTemplate = """components:
    mslt:
        components:
            population:
                - BasePopulation()
                - Mortality()
                - Disability()
            disease:
                - AcuteDisease('{0}', 'True')
                - AcuteDisease('anxiety', 'False')
                - AcuteDisease('depressive', 'False')
                - AcuteDisease('falls', 'False')
                #- AcuteDisease('ipv', 'False')
                - AcuteDisease('roadinjury', 'False')
                - AcuteDisease('selfharm', 'False')
            stage:
                - LockdownAcuteDisease('stage3and4')
            observer:
                - AcuteDisease('{0}')
                - AcuteDisease('anxiety')
                - AcuteDisease('depressive')
                - AcuteDisease('falls')
                #- AcuteDisease('ipv')
                - AcuteDisease('roadinjury')
                - AcuteDisease('selfharm')
                - MorbidityMortality()

configuration:
    input_data:
        artifact_path: C:\\Dev\\Repos\\COVID_PMSLT\\artifacts\\mslt_tobacco_non-maori.hdf
        input_draw_number: 0
        location: ''
    interpolation:
        validate: False
    population:
        # The population size here is the number of cohorts.
        # There are 22 age bins (0-4, 5-9, ..., 105-109) for females and for
        # males, making a total of 44 cohorts.
        population_size: 44
    time:
        start:
            year: 2021
            month: 1
            day: 15
        end:
            year: 2022
            month: 1
            day: 15
        step_size: 30.4166667  # In days
    lockdown:
        situation: '{0}'
        affects:
            anxiety: 1.88
            depressive: 1.16
            falls: 0.76
            #ipv: 1.539
            roadinjury: 0.65
            selfharm: 1.48
    observer:
        output_prefix: results/covid2_{1}/output"""

runFileNumber = 0
batchFile = open("batchFile.txt", "w")

for a, policy in enumerate(['AggressElim', 'ModerateElim', 'TightSupress', 'LooseSupress']):
    for b, uptake in enumerate(['60', '75', '90']):
        for c, tran1 in enumerate(['50', '75', '90']):
            for d, tran2 in enumerate(['50', '75', '90']):
                for e, loose in enumerate(['False', 'True']):
                    for f, rep in enumerate(['25', '043', '375']):
                        run = 'covid_param_policy{0}_param_vac_uptake{1}_param_vac1_tran_reduct{2}_param_vac2_tran_reduct{3}_param_trigger_loosen{4}_R0{5}_'.format(
                            policy, uptake, tran1, tran2, loose, rep)
                        index = '{0}{1}{2}{3}{4}{5}'.format(a, b, c, d, e, f)
                        f = open("covid_run_{0}.yaml".format(index), "w")
                        batchFile.write('simulate run model_specs/covid_run_{0}.yaml\n'.format(index))
                        #batchFile.write('simulate run -v model_specs/covid_run_{0}.yaml\n'.format(index))
                        f.write(specTemplate.format(run, index))
                        f.close()
                        runFileNumber = runFileNumber + 1
                        print(index, runFileNumber)
batchFile.close()
