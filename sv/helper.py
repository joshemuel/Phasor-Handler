import os
import numpy as np
import yaml
import pickle
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import Dict, List, Optional, Iterable
from scipy.signal import butter, filtfilt
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class SignalProcessor:
    @staticmethod
    def find_suite2p_run_folder(suite2p_base_dir: str, run_name: str) -> str:
        for folder in os.listdir(suite2p_base_dir):
            if run_name in folder and os.path.isdir(os.path.join(suite2p_base_dir, folder)):
                return os.path.join(suite2p_base_dir, folder)
        raise FileNotFoundError(f"No folder found for run '{run_name}' in {suite2p_base_dir}")

    @staticmethod
    def load_suite2p_outputs(run_folder: str, prob_threshold: float = 0.2, method="max_proj"):
        """Loads all standard Suite2p outputs and applies a cell probability threshold."""
        suite2p_dir = os.path.join(run_folder, 'suite2p', 'plane0')
        ops = np.load(os.path.join(suite2p_dir, 'ops.npy'), allow_pickle=True).item()
        stat = np.load(os.path.join(suite2p_dir, 'stat.npy'), allow_pickle=True)
        iscell_data = np.load(os.path.join(suite2p_dir, 'iscell.npy'), allow_pickle=True)
        F = np.load(os.path.join(suite2p_dir, 'F.npy'), allow_pickle=True)
        Fneu = np.load(os.path.join(suite2p_dir, 'Fneu.npy'), allow_pickle=True)
        F_chan2 = np.load(os.path.join(suite2p_dir, 'F_chan2.npy'), allow_pickle=True)
        spks = np.load(os.path.join(suite2p_dir, 'spks.npy'), allow_pickle=True)
        
        redcell_path = os.path.join(suite2p_dir, 'redcell.npy')
        redcell = np.load(redcell_path, allow_pickle=True) if os.path.exists(redcell_path) else np.zeros((len(stat), 2))
        
        try:
            img = ops.get(method)
        except KeyError as e:
            e.add_note("Using default 'max_proj' image.")
            img = ops.get('max_proj')
        
        iscell_mask = iscell_data[:, 1] >= prob_threshold

        return ops, stat, F, Fneu, F_chan2, redcell, spks, iscell_mask, img

    @staticmethod
    def find_matching_raw_dir(raw_base_dir: str, suite2p_base_name: str) -> str:
        for folder in os.listdir(raw_base_dir):
            if folder.startswith(suite2p_base_name + '-') and folder.endswith('.imgdir'):
                return os.path.join(raw_base_dir, folder, 'experiment_summary.pkl')
        raise FileNotFoundError(f"No raw folder found for base '{suite2p_base_name}' in {raw_base_dir}")

    @staticmethod
    def refine_rois_with_boxes(stat_original, exp_summary, rois_to_refine):
        import copy
        stat_refined = copy.deepcopy(stat_original)
        manual_rois = exp_summary.get("initial_roi_location", [])

        for manual_roi in manual_rois:
            _, corner1, corner2 = manual_roi
            x1, y1, _ = corner1
            x2, y2, _ = corner2
            
            # Find the Suite2p ROI whose center is inside this manual box
            for i, s2p_roi in enumerate(stat_refined):
                # Check if this ROI is in our target list
                if i not in rois_to_refine:
                    continue

                med_y, med_x = s2p_roi['med']
                if (x1 <= med_x < x2) and (y1 <= med_y < y2):
                    # This s2p_roi is a match AND is targeted for refinement
                    ypix, xpix = s2p_roi['ypix'], s2p_roi['xpix']
                    is_inside_box = (xpix >= x1) & (xpix < x2) & (ypix >= y1) & (ypix < y2)
                    
                    s2p_roi['ypix'] = ypix[is_inside_box]
                    s2p_roi['xpix'] = xpix[is_inside_box]
                    
                    s2p_roi['npix'] = len(s2p_roi['ypix'])
                    if s2p_roi['npix'] > 0:
                        s2p_roi['med'] = (np.median(s2p_roi['ypix']), np.median(s2p_roi['xpix']))
                    
                    break 
                    
        return stat_refined

    @staticmethod
    def extract_signals(
        stat,
        F: np.ndarray,
        Fneu: np.ndarray,
        F_chan2: np.ndarray,
        rois_to_process: Optional[Iterable[int]] = None,
        refine_roi_indices: Optional[Iterable[int]] = None,
        exp_summary: Optional[dict] = None,
        *,
        neuropil_coeff: float = 0.7,
        remove_breathing: bool = False,
        breathing_cutoff_hz: float = 0.25,
        fs: Optional[float] = None,
        raw: Optional[bool] = False,
        Fo: Optional[bool] = False
    ) -> Dict[int, np.ndarray]:
        
        if rois_to_process is None:
            rois_to_process = range(len(stat))

        if refine_roi_indices and exp_summary:
            print(f"Refined ROIs: {refine_roi_indices}")
            stat_processed = SignalProcessor.refine_rois_with_boxes(stat, exp_summary, refine_roi_indices)
        else:
            stat_processed = stat

        # sampling rate (Hz): infer from exp_summary['time_stamps'] if not provided
        if remove_breathing and fs is None and exp_summary is not None:
            ts = np.asarray(exp_summary.get("time_stamps", []), float)
            if ts.size >= 2:
                fs = 1.0 / np.median(np.diff(ts))
        if remove_breathing and (fs is None or not np.isfinite(fs)):
            # sane default if unknown
            fs = 10.0

        # build low-pass if requested
        if remove_breathing:
            wn = breathing_cutoff_hz / (fs / 2.0)
            wn = max(min(wn, 0.99), 1e-4)  # keep in (0,1)
            b, a = butter(N=2, Wn=wn, btype="lowpass")

            def lp(x: np.ndarray) -> np.ndarray:
                # x is 1D (time) here
                return filtfilt(b, a, x, axis=0)
        else:
            lp = lambda x: x  # no-op

        processed_signals: Dict[int, np.ndarray] = {}
        f_green: Dict[int, np.ndarray] = {}
        f_red: Dict[int, np.ndarray] = {}
        fo_processed: Dict[int, np.ndarray] = {}
        eps = 1e-6

        for roi_idx in rois_to_process:
            # neuropil subtraction
            f_green_corr = F[roi_idx]      - neuropil_coeff * Fneu[roi_idx]
            f_red_corr   = F_chan2[roi_idx] - neuropil_coeff * Fneu[roi_idx]

            # optional breathing suppression BEFORE baseline & ratio
            f_green_corr = lp(f_green_corr)
            f_red_corr   = lp(f_red_corr)

            # baseline on green
            f0_green = np.percentile(f_green_corr, 20)

            # ratio
            final_signal = (f_green_corr - f0_green) / (f_red_corr + eps)
            processed_signals[roi_idx] = final_signal
            f_green[roi_idx] = f_green_corr
            f_red[roi_idx] = f_red_corr

            # Take first 20% of processed signals
            fo_processed[roi_idx] = processed_signals[roi_idx][:int(0.2 * len(processed_signals[roi_idx]))]

        if not raw:
            if Fo:
                return processed_signals, fo_processed
            return processed_signals
        else:
            return f_green, f_red

    @staticmethod
    def find_stim_rois(stat, exp_summary):
        all_stimulation_boxes = exp_summary.get("stimulated_roi_location", [])
        stimulated_indices_by_event = []
        
        for stim_event_boxes in all_stimulation_boxes:
            rois_for_this_event = []
            for box in stim_event_boxes:
                _, corner1, corner2 = box
                x1, y1, _ = corner1
                x2, y2, _ = corner2
                
                for i, s2p_roi in enumerate(stat):
                    med_y, med_x = s2p_roi['med']
                    if (x1 <= med_x < x2) and (y1 <= med_y < y2):
                        if i not in rois_for_this_event:
                            rois_for_this_event.append(i)
            stimulated_indices_by_event.append(rois_for_this_event)
            
        return stimulated_indices_by_event
    

class SignalPlotter:
    @staticmethod
    def plot_all_runs(suite2p_base_dir, raw_base_dir, suite2p_base_name, run_names, cell_prob, label="suite2p", method="max_proj"):
        fig, axes = plt.subplots(4, 3, figsize=(18, 24))
        axes = axes.flatten()

        # Find and load the corresponding experiment summary
        try:
            raw_dir = SignalProcessor.find_matching_raw_dir(raw_base_dir, suite2p_base_name)
            if raw_dir:
                with open(Path(raw_dir), 'rb') as f:
                    exp_summary = pickle.load(f)
            else:
                print(f"Warning: Could not find matching raw directory for {suite2p_base_name}")
                exp_summary = {}
        except Exception as e:
            print(f"Error loading experiment summary: {e}")
            exp_summary = {}


        for idx, run_name in enumerate(run_names):
            if idx >= len(axes):
                break
            
            ax = axes[idx]
            try:
                run_folder = SignalProcessor.find_suite2p_run_folder(suite2p_base_dir, run_name)
                ops, stat, F, Fneu, F_chan2, redcell, spks, iscell_mask, max_proj = SignalProcessor.load_suite2p_outputs(run_folder, prob_threshold=cell_prob, method=method)

                ax.imshow(max_proj, cmap='gray')

                # Overlay Suite2p masks
                mask_overlay = np.zeros((ops['Ly'], ops['Lx'], 4))
                cell_color = [0, 1, 0, 1]
                non_cell_color = [1, 0, 0, 1]
                for i, roi in enumerate(stat):
                    if iscell_mask[i]:
                        mask_overlay[roi['ypix'], roi['xpix']] = cell_color
                    else:
                        mask_overlay[roi['ypix'], roi['xpix']] = non_cell_color
                ax.imshow(mask_overlay, alpha=0.1)

                for i, roi in enumerate(stat):
                    x_mean = np.mean(roi['xpix'])
                    y_mean = np.mean(roi['ypix'])
                    if label == "suite2p":
                        ax.text(x_mean, y_mean, str(i), color='white', fontsize=8, ha='center', va='center', weight='bold')

                # Overlay initial rectangular ROI locations
                for roi in exp_summary.get("initial_roi_location", []):
                    roi_id, corner1, corner2 = roi
                    x1, y1, _ = corner1
                    x2, y2, _ = corner2
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=1.5, edgecolor='yellow', facecolor='none')
                    ax.add_patch(rect)
                    if label == "original":
                        ax.text(x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2, str(roi_id), color='yellow', fontsize=8, ha='center', va='center', weight='bold')

                # Overlay stimulated rectangular ROI locations
                for stim_event in exp_summary.get("stimulated_roi_location", []):
                    for roi in stim_event:
                        roi_id, corner1, corner2 = roi
                        x1, y1, _ = corner1
                        x2, y2, _ = corner2
                        rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=1.5, edgecolor='cyan', facecolor='none')
                        ax.add_patch(rect)
                        if label == "stimulated":
                            ax.text(x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2, str(roi_id), color='cyan', fontsize=8, ha='center', va='center', weight='bold')

                ax.set_title(f"{run_name} (Cell Prob >= {cell_prob})")

            except Exception as e:
                print(f"Skipping {run_name}: {e}")
                ax.set_title(f"{run_name}\n(Data not found)", fontsize=10)
            
            finally:
                ax.axis("off")

        # Hide any unused axes
        for j in range(len(run_names), len(axes)):
            axes[j].axis("off")

        plt.suptitle(f"Max Projections for {suite2p_base_name}", fontsize=20, y=1.03)
        plt.tight_layout(rect=[0, 0, 1, 0.98], pad=2.0)
        plt.show()

    @staticmethod
    def plot_single_run(ax, suite2p_base_dir, raw_base_dir, suite2p_base_name, selected_run, cell_prob, label="suite2p", method="max_proj"):

        try:
            raw_dir = SignalProcessor.find_matching_raw_dir(raw_base_dir, suite2p_base_name)
            if raw_dir:
                with open(Path(raw_dir), 'rb') as f:
                    exp_summary = pickle.load(f)
            else:
                exp_summary = {}

            run_folder = SignalProcessor.find_suite2p_run_folder(suite2p_base_dir, selected_run)
            ops, stat, F, Fneu, F_chan2, redcell, spks, iscell_mask, max_proj = SignalProcessor.load_suite2p_outputs(run_folder, prob_threshold=cell_prob, method=method)

            ax.imshow(max_proj, cmap='gray')

            # Overlay Suite2p masks
            mask_overlay = np.zeros((ops['Ly'], ops['Lx'], 4))
            cell_color = [0, 1, 0, 1]
            non_cell_color = [1, 0, 0, 1]
            for i, roi in enumerate(stat):
                if iscell_mask[i]:
                    mask_overlay[roi['ypix'], roi['xpix']] = cell_color
                else:
                    mask_overlay[roi['ypix'], roi['xpix']] = non_cell_color
            ax.imshow(mask_overlay, alpha=0.1)

            for i, roi in enumerate(stat):
                x_mean = np.mean(roi['xpix'])
                y_mean = np.mean(roi['ypix'])
                if label == "suite2p":
                    ax.text(x_mean, y_mean, str(i), color='white', fontsize=8, ha='center', va='center', weight='bold')

            # Overlay initial rectangular ROI locations
            for roi in exp_summary.get("initial_roi_location", []):
                roi_id, corner1, corner2 = roi
                x1, y1, _ = corner1
                x2, y2, _ = corner2
                rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=1.5, edgecolor='yellow', facecolor='none')
                ax.add_patch(rect)
                if label == "original":
                    ax.text(x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2, str(roi_id), color='yellow', fontsize=8, ha='center', va='center', weight='bold')
            
            # Overlay stimulated rectangular ROI locations
            for stim_event in exp_summary.get("stimulated_roi_location", []):
                for roi in stim_event:
                    roi_id, corner1, corner2 = roi
                    x1, y1, _ = corner1
                    x2, y2, _ = corner2
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=1.5, edgecolor='cyan', facecolor='none')
                    ax.add_patch(rect)
                    if label == "stimulated":
                        ax.text(x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2, str(roi_id), color='cyan', fontsize=8, ha='center', va='center', weight='bold')

            ax.set_title(f"Max Projection for {selected_run} (Cell Prob >= {cell_prob})", fontsize=16)
            ax.axis("off")

        except Exception as e:
            print(f"Could not generate plot for {selected_run}: {e}")
            ax.set_title(f"{selected_run}\n(Data not found or error occurred)", fontsize=10)
            ax.axis("off")

        plt.tight_layout()

        return ax

    def plot_interactive_run(suite2p_base_dir, raw_base_dir, suite2p_base_name, selected_run, cell_prob):
        def load_tiff_series(plane_dir, tiff_folder_name):
            tiff_path = os.path.join(plane_dir, tiff_folder_name)
            if not os.path.isdir(tiff_path): return None
            tiff_files = sorted([f for f in os.listdir(tiff_path) if f.endswith('.tif')])
            if not tiff_files: return None
            movie_parts = [tf.imread(os.path.join(tiff_path, f)) for f in tiff_files]
            return np.concatenate(movie_parts, axis=0)

        try:
            run_folder = SignalProcessor.find_suite2p_run_folder(suite2p_base_dir, selected_run)
            plane_dir = os.path.join(run_folder, 'suite2p', 'plane0')
            ops, stat, _, _, _, _, _, iscell_mask, _ = SignalProcessor.load_suite2p_outputs(run_folder, prob_threshold=cell_prob)

            raw_dir = SignalProcessor.find_matching_raw_dir(raw_base_dir, suite2p_base_name)
            exp_summary = {}
            if raw_dir:
                with open(Path(raw_dir) / 'experiment_summary.pkl', 'rb') as f:
                    exp_summary = pickle.load(f)

            # Load movies
            movie_chan1 = load_tiff_series(plane_dir, 'reg_tif')
            movie_chan2 = load_tiff_series(plane_dir, 'reg_tif_chan2')
            
            if movie_chan1 is None and movie_chan2 is None:
                raise FileNotFoundError("No registered TIFF movies found.")

            # --- Create the Plot ---
            fig, ax = plt.subplots(figsize=(10, 10))
            plt.subplots_adjust(left=0.2, bottom=0.15)

            # Create a 3-channel RGB image for display
            frame_data = np.zeros((ops['Ly'], ops['Lx'], 3), dtype=np.uint16)
            im = ax.imshow(frame_data)

            # --- Draw Static Overlays ---
            # ... (your ROI overlay logic) ...

            # --- Create Widgets ---
            ax_slider = plt.axes([0.25, 0.05, 0.6, 0.03])
            frame_slider = Slider(ax=ax_slider, label='Frame', valmin=0, valmax=ops['nframes'] - 1, valinit=0, valstep=1)
            
            ax_radio = plt.axes([0.025, 0.7, 0.15, 0.15])
            radio_buttons = RadioButtons(ax_radio, ('Both', 'Green (Chan1)', 'Red (Chan2)'))

            def update(val):
                frame_num = int(frame_slider.val)
                view = radio_buttons.value_selected
                
                # Reset frame data
                frame_data.fill(0)
                
                if view in ['Both', 'Green (Chan1)'] and movie_chan1 is not None:
                    frame_data[:,:,1] = movie_chan1[frame_num] # Green channel
                if view in ['Both', 'Red (Chan2)'] and movie_chan2 is not None:
                    frame_data[:,:,0] = movie_chan2[frame_num] # Red channel
                
                # Normalize for display
                clim_max = np.percentile(frame_data[frame_data > 0], 99.5) if np.any(frame_data > 0) else 1
                im.set_data((frame_data / clim_max).clip(0, 1))
                ax.set_title(f"Run: {selected_run} | Frame: {frame_num} | View: {view}")
                fig.canvas.draw_idle()

            frame_slider.on_changed(update)
            radio_buttons.on_clicked(update)
            
            update(0) # Initial draw
            plt.show()

        except Exception as e:
            print(f"Could not generate plot for {selected_run}: {e}")
