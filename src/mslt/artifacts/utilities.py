from pathlib import Path


def get_data_dir(population):
    here = Path(__file__).resolve()
    return here.parent / population
