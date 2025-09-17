import suite2p
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description="Suite2p registration runner (minimal)")
parser.add_argument("--movie", required=True, type=str, help="Path to the single TIF to process")
parser.add_argument("--outdir", type=str, default=None, help="(Optional) output folder. Default: <movie_dir>/<movie_stem>_regscan")
parser.add_argument("--param", action="append", default=[], help="Suite2p parameter as key=value (repeat for multiple)")
args = parser.parse_args()

def parse_param_list(param_list):
    d = {}
    for p in param_list:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        try:
            if v.startswith("[") and v.endswith("]"):
                d[k] = eval(v)
            elif "." in v:
                d[k] = float(v)
            else:
                d[k] = int(v)
        except Exception:
            d[k] = v
    return d

param_dict = parse_param_list(args.param)

movie = Path(args.movie).expanduser().resolve()
root_out = (Path(args.outdir).expanduser().resolve()
            if args.outdir is not None
            else movie.parent)
root_out.mkdir(exist_ok=True, parents=True)

ops = suite2p.default_ops()
ops.update({
    "nplanes": 1,
    "nchannels": 2,
    "functional_chan": 1,
    "fs": 10.535,
    "tau": 0.7,
    "align_by_chan": 2,
    "do_registration": 1,
    "reg_tif": True,
    "reg_tif_chan2": True,
    "keep_movie_raw": True,
    "data_path": [str(movie.parent)],
    "save_path0": str(root_out),
    "sparse_mode": True,
    "spatial_scale": 2,
    "anatomical_only": 1,
    "threshold_scaling": 0.5,
    "soma_crop": True,
    "neuropil_extract": True
})
ops.update(param_dict)

db = {
    "data_path": [str(movie.parent)],
    "tiff_list": [movie.name],
    "save_path0": str(root_out),
    "fast_disk": str(root_out),
    "subfolders": [],
}

suite2p.run_s2p(ops=ops, db=db)