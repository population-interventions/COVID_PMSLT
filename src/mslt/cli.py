import logging
from pathlib import Path

import click

from mslt.artifacts import assemble_artifacts
from mslt.components import run_many


@click.command()
@click.argument('scenario', type=click.Choice(['minimal', 'uncertainty']))
def make_artifacts(scenario):
    """Generate artifacts for the MSLT tobacco intervention simulations."""
    logging.basicConfig(level=logging.INFO)

    output_path = Path('.').resolve() / 'artifacts'
    output_path.mkdir(exist_ok=True)
    draws = 0 if scenario == 'minimal' else 100

    logging.info(f'Generating artifact for scenario {scenario} with {draws} '
                 f'draws at {str(output_path)}')

    assemble_artifacts(draws, output_path)


@click.command()
@click.option('-d', '--draws', default=5, metavar='NUM',
              help='The number of draws for which to run simulations')
@click.option('-s', '--spawn', default=1, metavar='NUM',
              help='The number of simulations to run in parallel')
@click.argument('spec_file', type=click.Path(exists=True), nargs=-1)
def run_uncertainty_analysis(draws, spawn, spec_file):
    """
    Run MSLT tobacco intervention simulations for multiple value draws.

    You can provide any number of model specification files.
    """
    logging.basicConfig(level=logging.INFO)
    run_many(spec_file, draws, spawn)
