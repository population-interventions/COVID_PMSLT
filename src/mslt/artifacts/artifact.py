import datetime
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from vivarium.framework.artifact import hdf
from vivarium.framework.artifact import Artifact

from mslt.artifacts.population import Population
from mslt.artifacts.disease import Diseases
from mslt.artifacts.stage import Stages
from mslt.artifacts.disease_covid import Covid
from mslt.artifacts.risk_factor import Tobacco
from mslt.artifacts.uncertainty import Normal, Beta, LogNormal
from mslt.artifacts.utilities import get_data_dir

YEAR_START = 2021
RANDOM_SEED = 49430
WRITE_CSV = True

def output_csv_mkdir(data, path):
    """
    Wrapper for pandas .to_csv() method to create directory for path if it
    doesn't already exist.
    """
    output_path = Path('.').resolve() / 'artifacts' / (path + '.csv')
    out_folder = os.path.dirname(output_path)

    if not os.path.exists(out_folder):
        os.mkdir(out_folder)

    print(output_path)
    data.to_csv(output_path)


def check_for_bin_edges(df):
    """
    Check that lower (inclusive) and upper (exclusive) bounds for year and age
    are defined as table columns.
    """

    if 'age_start' in df.columns and 'year_start' in df.columns:
        return df
    else:
        raise ValueError('Table does not have bins')


def write_table(artifact, path, data):
    """
    Write a data table to an artifact, after ensuring that it doesn't contain
    any NA values.

    :param artifact: The artifact object.
    :param path: The table path.
    :param data: The table data.
    """
    if np.any(data.isna()):
        msg = 'NA values in table {} for {}'.format(path, artifact.path)
        raise ValueError(msg)

    logger = logging.getLogger(__name__)
    logger.info('{} Writing table {} to {}'.format(
        datetime.datetime.now().strftime("%H:%M:%S"), path, artifact.path))

    #Add age,sex,year etc columns to multi index
    col_index_filters = ['year','age','sex','year_start','year_end','age_start','age_end']
    data.set_index([col_name for col_name in data.columns if col_name in col_index_filters], inplace =True)
    
    #Convert wide to long for tobacco
    # TODO: Check if still needed?
    #if 'value' not in data.columns:
    #    data = pd.melt(data.reset_index(), id_vars=data.index.names,var_name = 'measure').\
    #    set_index(data.index.names+['measure'])

    if WRITE_CSV:
      output_csv_mkdir(data, path)
    artifact.write(path, data)


def assemble_artifacts(num_draws, output_path: Path, seed: int = RANDOM_SEED):
    """
    Assemble the data artifacts required to simulate the various tobacco
    interventions.

    Parameters
    ----------
    num_draws
        The number of random draws to sample for each rate and quantity,
        for the uncertainty analysis.
    output_path
        The path to the artifact being assembled.
    seed
        The seed for the pseudo-random number generator used to generate the
        random samples.

    """
    data_dir = get_data_dir('data')
    prng = np.random.RandomState(seed=seed)
    logger = logging.getLogger(__name__)

    # Instantiate components for the non-Maori population.
    pop = Population(data_dir, YEAR_START)
    diseaseList = Diseases(data_dir, YEAR_START, pop.year_end)

    # Define data structures to record the samples from the unit interval that
    # are used to sample each rate/quantity, so that they can be correlated
    # across both populations.
    smp_yld = prng.random_sample(num_draws)
    smp_chronic_apc = {}
    smp_chronic_i = {}
    smp_chronic_r = {}
    smp_chronic_f = {}
    smp_chronic_yld = {}
    smp_chronic_prev = {}
    smp_acute_f = {}
    smp_acute_yld = {}
    smp_tob_dis_tbl = {}

    # Define the sampling distributions in terms of their family and their
    # *relative* standard deviation; they will be used to draw samples for
    # both populations.
    dist_yld = LogNormal(sd_pcnt=10)
    dist_chronic_apc = Normal(sd_pcnt=0.5)
    dist_chronic_i = Normal(sd_pcnt=5)
    dist_chronic_r = Normal(sd_pcnt=5)
    dist_chronic_f = Normal(sd_pcnt=5)
    dist_chronic_yld = Normal(sd_pcnt=10)
    dist_chronic_prev = Normal(sd_pcnt=5)
    dist_acute_f = Normal(sd_pcnt=10)
    dist_acute_yld = Normal(sd_pcnt=10)

    logger.info('{} Generating samples'.format(
        datetime.datetime.now().strftime("%H:%M:%S")))

    for name, disease_nm in diseaseList.chronic.items():
        # Draw samples for each rate/quantity for this disease.
        smp_chronic_apc[name] = prng.random_sample(num_draws)
        smp_chronic_i[name] = prng.random_sample(num_draws)
        smp_chronic_r[name] = prng.random_sample(num_draws)
        smp_chronic_f[name] = prng.random_sample(num_draws)
        smp_chronic_yld[name] = prng.random_sample(num_draws)
        smp_chronic_prev[name] = prng.random_sample(num_draws)

        # Also draw samples for the RR associated with tobacco smoking.
        smp_tob_dis_tbl[name] = prng.random_sample(num_draws)

    for name, disease_nm in diseaseList.acute.items():
        # Draw samples for each rate/quantity for this disease.
        smp_acute_f[name] = prng.random_sample(num_draws)
        smp_acute_yld[name] = prng.random_sample(num_draws)

        # Also draw samples for the RR associated with tobacco smoking.
        smp_tob_dis_tbl[name] = prng.random_sample(num_draws)

    # Now write all of the required tables
    artifact_fmt = 'pmslt_artifact.hdf'
    artifact_file = output_path / artifact_fmt

    logger.info('{} Generating artifacts'.format(
        datetime.datetime.now().strftime("%H:%M:%S")))

    # Initialise each artifact file.
    for path in [artifact_file]:
        if path.exists():
            path.unlink()

    # Write the data tables to each artifact file.
    art_nm = Artifact(str(artifact_file))

    logger.info('{} Writing population tables'.format(
        datetime.datetime.now().strftime("%H:%M:%S")))

    # Write the main population tables.
    write_table(art_nm, 'population.structure',
                 pop.get_population())
    write_table(art_nm, 'cause.all_causes.disability_rate',
                 pop.sample_disability_rate_from(dist_yld, smp_yld))
    write_table(art_nm, 'cause.all_causes.mortality',
                 pop.get_mortality_rate())
    
    # Write the chronic disease tables.
    for name, disease_nm in diseaseList.chronic.items():
        logger.info('{} Writing tables for {}'.format(
            datetime.datetime.now().strftime("%H:%M:%S"), name))

        write_table(art_nm, 'chronic_disease.{}.incidence'.format(name),
                     disease_nm.sample_i_from(
                         dist_chronic_i, dist_chronic_apc,
                         smp_chronic_i[name], smp_chronic_apc[name]))
        write_table(art_nm, 'chronic_disease.{}.remission'.format(name),
                     disease_nm.sample_r_from(
                         dist_chronic_r, dist_chronic_apc,
                         smp_chronic_r[name], smp_chronic_apc[name]))
        write_table(art_nm, 'chronic_disease.{}.mortality'.format(name),
                     disease_nm.sample_f_from(
                         dist_chronic_f, dist_chronic_apc,
                         smp_chronic_f[name], smp_chronic_apc[name]))
        write_table(art_nm, 'chronic_disease.{}.morbidity'.format(name),
                     disease_nm.sample_yld_from(
                         dist_chronic_yld, dist_chronic_apc,
                         smp_chronic_yld[name], smp_chronic_apc[name]))
        write_table(art_nm, 'chronic_disease.{}.prevalence'.format(name),
                     disease_nm.sample_prevalence_from(
                         dist_chronic_prev, smp_chronic_prev[name]))

    # Write the acute disease tables.
    for name, disease_nm in diseaseList.acute.items():
        logger.info('{} Writing tables for {}'.format(
            datetime.datetime.now().strftime("%H:%M:%S"), name))

        write_table(art_nm, 'acute_disease.{}.mortality'.format(name),
                     disease_nm.sample_excess_mortality_from(
                         dist_acute_f, smp_acute_f[name]))
        write_table(art_nm, 'acute_disease.{}.morbidity'.format(name),
                     disease_nm.sample_disability_from(
                         dist_acute_yld, smp_acute_yld[name]))

    # Add lockdowns
    logger.info('{} Writing lockdown tables'.format(
        datetime.datetime.now().strftime("%H:%M:%S")))
    
    Stages(art_nm, data_dir, YEAR_START, pop.year_end, write_table, num_draws)

    # Do some ad hoc stuff for covid
    logger.info('{} Writing covid tables'.format(
        datetime.datetime.now().strftime("%H:%M:%S")))
    
    Covid(art_nm, data_dir, YEAR_START, pop.year_end, pop.get_population(), write_table, num_draws)

    print(artifact_file)
