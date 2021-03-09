from pathlib import Path


def get_model_specification_template_file():
    here = Path(__file__).resolve()
    return here.parent / 'templates/yaml_template.in'


def get_reduce_acmr_specification_template_file():
    here = Path(__file__).resolve()
    return here.parent / 'templates/mslt_reduce_acmr.in'


def get_reduce_chd_specification_template_file():
    here = Path(__file__).resolve()
    return here.parent / 'templates/mslt_reduce_chd.in'
