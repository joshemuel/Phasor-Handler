"""Simple plotting utility for toolbox `trace.txt` files.

Usage:
	python plot.py input_trace.txt output.pdf

The script produces a multi-page PDF with:
 - Page 1: heatmap of all ROI traces (frames x ROIs)
 - Page 2: mean trace and standard deviation band
 - Subsequent pages: individual ROI traces with basic stats

Dependencies: pandas, numpy, matplotlib
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def read_trace(path: Path) -> pd.DataFrame:
	# trace.txt is a tab-delimited file with a header row
	return pd.read_csv(path, sep='\t', index_col=0)


def make_overview_heatmap(df: pd.DataFrame, pdf: PdfPages):
	# Select only columns that represent Trace_ROI* or numeric columns after frame
	# Many generated files have columns like 'Trace_ROI1', try to select them.
	trace_cols = [c for c in df.columns if 'Trace' in c or c.startswith('Trace_')]
	if not trace_cols:
		# fall back to every column except any that look like mean channels
		trace_cols = [c for c in df.columns if 'Mean' not in c]

	data = df[trace_cols].to_numpy()

	fig, ax = plt.subplots(figsize=(8.5, 11))
	im = ax.imshow(data.T, aspect='auto', cmap='viridis', interpolation='nearest')
	ax.set_ylabel('ROI')
	ax.set_xlabel('Frame')
	ax.set_title('ROI traces (heatmap)')
	fig.colorbar(im, ax=ax, orientation='vertical', label='Trace value')
	pdf.savefig(fig)
	plt.close(fig)


def make_summary_page(df: pd.DataFrame, pdf: PdfPages):
	trace_cols = [c for c in df.columns if 'Trace' in c or c.startswith('Trace_')]
	data = df[trace_cols]
	mean = data.mean(axis=1)
	std = data.std(axis=1)

	fig, ax = plt.subplots(figsize=(8.5, 11))
	ax.plot(df.index, mean, color='black', label='Mean')
	ax.fill_between(df.index, mean-std, mean+std, color='gray', alpha=0.3, label='±1 std')
	ax.set_xlabel('Frame')
	ax.set_ylabel('Trace')
	ax.set_title('Mean ROI trace ±1 std')
	ax.legend()
	pdf.savefig(fig)
	plt.close(fig)


def make_individual_pages(df: pd.DataFrame, pdf: PdfPages, max_per_page: int = 6):
	trace_cols = [c for c in df.columns if 'Trace' in c or c.startswith('Trace_')]
	n = len(trace_cols)
	frames = df.index
	for i, col in enumerate(trace_cols):
		fig, ax = plt.subplots(figsize=(8.5, 11))
		ax.plot(frames, df[col], lw=0.8)
		ax.set_title(f'ROI {i+1}: {col}')
		ax.set_xlabel('Frame')
		ax.set_ylabel('Trace')
		# simple stats
		ax.text(0.98, 0.02, f'mean={df[col].mean():.4f}\nstd={df[col].std():.4f}',
				ha='right', va='bottom', transform=ax.transAxes, fontsize=8,
				bbox=dict(facecolor='white', alpha=0.6, edgecolor='none'))
		pdf.savefig(fig)
		plt.close(fig)


def main(argv):
	if len(argv) < 3:
		print('Usage: python plot.py input_trace.txt output.pdf')
		return 2

	in_path = Path(argv[1])
	out_path = Path(argv[2])
	if not in_path.exists():
		print(f'Input file {in_path} not found')
		return 2

	df = read_trace(in_path)

	with PdfPages(out_path) as pdf:
		make_overview_heatmap(df, pdf)
		make_summary_page(df, pdf)
		make_individual_pages(df, pdf)

	print(f'Wrote {out_path}')
	return 0


if __name__ == '__main__':
	raise SystemExit(main(sys.argv))

