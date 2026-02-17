"""
T-RKG Datasets

Loaders for real-world datasets to validate T-RKG capabilities.
"""

from trkg.datasets.enron import (
    EnronDatasetLoader,
    load_enron_dataset,
    ENRON_EMPLOYEES,
)

__all__ = [
    'EnronDatasetLoader',
    'load_enron_dataset',
    'ENRON_EMPLOYEES',
]
