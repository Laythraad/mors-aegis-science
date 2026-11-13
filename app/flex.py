"""Source-checked FLEX table and reproducible descriptive statistics."""
import csv
import hashlib
import io
from pathlib import Path

import numpy as np

from app.bass import finite_number

ROOT = Path(__file__).resolve().parent / 'static'
EXPECTED = '70a77cad9a9fd6aed5d05f95366a87366a50cb2dd4d2e0467ce35cde2adb7469'


def analyze(fuel='', pressure='', diluent=''):
    if fuel not in ('', 'Methanol', 'Heptane') or pressure not in ('', 'low', 'normal', 'high', 'unknown') or diluent not in ('', 'none', 'CO2', 'He', 'mixed', 'unknown'):
        raise ValueError('Invalid FLEX filter')
    content = (ROOT / 'flex-psi69-full.csv').read_bytes()
    if hashlib.sha256(content).hexdigest() != EXPECTED:
        raise RuntimeError('FLEX normalized source checksum mismatch')
    rows = list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline='')))
    selected = []
    for row in rows:
        p = finite_number(row['pressure_mmHg'])
        band = 'unknown' if p is None or p < 0 else 'low' if p < 650 else 'normal' if p < 1000 else 'high'
        co2, he = finite_number(row['carbon_dioxide_mole_fraction']), finite_number(row['helium_mole_fraction'])
        gas = 'unknown' if co2 is None or he is None else 'mixed' if co2 > 0 and he > 0 else 'CO2' if co2 > 0 else 'He' if he > 0 else 'none'
        if (fuel and row['fuel'] != fuel) or (pressure and band != pressure) or (diluent and gas != diluent):
            continue
        rate = finite_number(row['burning_rate_mm_s'])
        diameter = finite_number(row['initial_droplet_diameter_mm'])
        selected.append({'id': row['id'], 'fuel': row['fuel'], 'pressure_mmHg': p, 'pressure_band': band,
                         'diluent': gas, 'diameter_mm': diameter, 'rate_mm2_s': rate, 'quality_flags': row['quality_flags']})
    values = np.array([r['rate_mm2_s'] for r in selected if r['rate_mm2_s'] is not None], dtype=float)
    interval = None
    if len(values) >= 5:
        rng = np.random.default_rng(69)
        means = values[rng.integers(0, len(values), size=(1000, len(values)))].mean(axis=1)
        interval = [float(x) for x in np.quantile(means, [0.025, 0.975])]
    return {'source': 'https://doi.org/10.60555/mbq8-0451', 'source_sha256': EXPECTED,
            'total_rows': len(rows), 'selected_count': len(selected), 'valid_rate_count': len(values),
            'missing_rate_count': len(selected)-len(values), 'mean_rate_mm2_s': float(values.mean()) if len(values) else None,
            'ci95': interval, 'seed': 69, 'resamples': 1000, 'rows': selected,
            'filters': {'fuel': fuel, 'pressure': pressure, 'diluent': diluent},
            'limitations': 'Descriptive results, not causal. Conditions vary within groups; bootstrap assumes independent sampled records and does not include measurement uncertainty. Corrected normalized values and quality flags are documented separately.'}
