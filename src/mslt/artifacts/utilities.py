import pandas as pd
import numpy as np

from pathlib import Path


def get_data_dir(population):
    here = Path(__file__).resolve()
    return here.parent / population


def UnstackDraw(df):
    df = df.sort_values(['year_start', 'age_start', 'sex', 'draw'])
    df = df.set_index(['year_start',  'year_end', 'age_start', 'age_end', 'sex', 'draw'])
    df = df.unstack(level='draw')
    df = df.droplevel(0, axis=1)
    col_frame = df.columns.to_frame()
    col_frame = col_frame.reset_index(drop=True)
    col_frame['draw'] = 'draw_' + col_frame['draw'].astype(str)
    df.columns = pd.Index(col_frame['draw'])
    df.columns.name = None
    df = df.reset_index()
    return df