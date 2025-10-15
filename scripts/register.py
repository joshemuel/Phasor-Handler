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
        # Map GUI parameter names to suite2p names
        if k == "n_channels":
            k = "nchannels"
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

# Set reasonable defaults (will be overridden by GUI params)
default_ops = {
    "nplanes": 1,
    "nchannels": 2,  # Default to 2 channels
    "functional_chan": 1,
    "fs": 10.535,
    "tau": 0.7,
    "align_by_chan": 2,
    "do_registration": 1,
    "reg_tif": True,
    "reg_tif_chan2": True if param_dict.get("n_channels", 2) >= 2 else False,
    "keep_movie_raw": True,
    "data_path": [str(movie.parent)],
    "save_path0": str(root_out),
    "sparse_mode": True,
    "spatial_scale": 0,
    "anatomical_only": 1,
    "threshold_scaling": 0.5,
    "soma_crop": True,
    "neuropil_extract": True
}

ops.update(default_ops)
ops.update(param_dict)  # GUI params override defaults

# Set channel-dependent parameters based on nchannels
n_channels = ops.get("nchannels", 1)
if n_channels >= 2:
    ops["align_by_chan"] = ops.get("align_by_chan", 2)
    ops["reg_tif_chan2"] = True
    ops["1Preg"] = ops.get("1Preg", 1)
else:
    # For single channel, don't try to register/save channel 2
    ops["align_by_chan"] = 1
    ops["reg_tif_chan2"] = False
    ops["1Preg"] = 0

db = {
    "data_path": [str(movie.parent)],
    "tiff_list": [movie.name],
    "save_path0": str(root_out),
    "fast_disk": str(root_out),
    "subfolders": [],
}

suite2p.run_s2p(ops=ops, db=db)