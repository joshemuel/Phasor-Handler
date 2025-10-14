import yaml
import numpy as np
import os
import xml.etree.ElementTree as ET
import re
import csv
import argparse
from pathlib import Path
import pickle
import json

# -------------- INPUTS --------------
parser = argparse.ArgumentParser(description='Process a folder of .yaml files.')
parser.add_argument('-f', '--folder_path', required=True, type=str, help='Path to the folder containing .yaml files')
args = parser.parse_args()

folder_path = args.folder_path

# ------------- FUNCTIONS -------------
def open_overwrite(path, *args, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    return open(path, *args, **kwargs) 

def load_classes(yaml_path):
    classes = {}
    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split on "StartClass:", then re-add it to each chunk
    chunks = ["StartClass:" + c for c in content.split("StartClass:") if c.strip()]

    for chunk in chunks:
        try:
            data = yaml.safe_load(chunk)

            if not isinstance(data, dict):
                continue

            class_data = data.get("StartClass", {})
            class_name = class_data.get("ClassName")
            if not class_name:
                continue

            # ✅ If class_name already exists, turn it into a list
            if class_name in classes:
                if isinstance(classes[class_name], list):
                    classes[class_name].append(class_data)
                else:
                    classes[class_name] = [classes[class_name], class_data]
            else:
                classes[class_name] = class_data

        except yaml.YAMLError as e:
            print("YAML parse error in chunk:\n", chunk[:200], "...", e)

    return classes

def get_organized_experiment_data(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    chunks = content.strip().split("theTimepointIndex:")

    # --- 1. Parse the Main Data Header ---
    # The header is the very first part, before any time points.
    header_chunk = chunks[0]
    header_metadata = yaml.safe_load(header_chunk.split("EndClass:")[0] + "EndClass: CDataTableHeaderRecord70")
    header = header_metadata.get("StartClass", {})

    # --- 2. Parse the Initial ROI Definitions (from Timepoint 0) ---
    # These are the ROIs defined before any stimulations.
    initial_rois = {}
    if len(chunks) > 1:
        timepoint_zero_chunk = "theTimepointIndex:" + chunks[1]
        sub_chunks = timepoint_zero_chunk.split("StartClass:")
        
        annotations = []
        for ann_chunk in sub_chunks[1:]:
            ann_data = yaml.safe_load("StartClass:" + ann_chunk)
            if ann_data and "StartClass" in ann_data:
                annotations.append(ann_data["StartClass"])
        
        # Organize the initial ROIs into a clean dictionary by their index
        for i, ann in enumerate(annotations):
            if ann.get("ClassName") == 'CCubeAnnotation70':
                roi_id = ann['mRegionIndex']
                if i + 1 < len(annotations):
                    initial_rois[roi_id] = annotations[i + 1]

    # --- 3. Parse and Filter for Stimulation Events (Timepoint 1 onwards) ---
    stimulation_events = []
    # The loop now correctly starts from the third chunk (index 2), skipping the header and timepoint 0.
    for chunk in chunks[2:]:
        full_chunk = "theTimepointIndex:" + chunk
        try:
            sub_chunks = full_chunk.split("StartClass:")
            metadata_part = sub_chunks[0]
            timepoint_metadata = yaml.safe_load(metadata_part)

            annotations = []
            for ann_chunk in sub_chunks[1:]:
                ann_data = yaml.safe_load("StartClass:" + ann_chunk)
                if ann_data and "StartClass" in ann_data:
                    annotations.append(ann_data["StartClass"])
            timepoint_metadata["annotations"] = annotations

            # Now, check if this timepoint is a stimulation event
            frap_annotation = next((ann for ann in annotations if ann.get("ClassName") == "CFRAPRegionAnnotation70"), None)
            
            if frap_annotation:
                stimulation_events.append({
                    "timepoint_index": timepoint_metadata["theTimepointIndex"],
                    "stimulation_data": frap_annotation,
                    "roi_annotations": [ann for ann in annotations if ann.get("ClassName") != "CFRAPRegionAnnotation70"]
                })
        except yaml.YAMLError as e:
            print(f"Skipping problematic chunk due to YAML error: {e}")
            continue

    return {
        "header": header,
        "initial_rois": initial_rois,
        "stimulation_events": stimulation_events
    }

def parse_stimulation_xml(xml_string):
    """
    Cleans and parses the escaped XML string from the annotation file.

    Args:
        xml_string (str): The XML data string with escaped characters.

    Returns:
        dict: A dictionary containing the extracted metadata, or None if parsing fails.
    """
    # --- 1. Clean the XML String ---
    # This replacement map handles the specific escaped characters.
    replacements = {
        '_#60;': '<',
        '_#62;': '>',
        '_#34;': '"',
        '_#32;': ' ',
        '_#10;': '\n',
        '_#58;': ':',
        '_#91;': '[',
        '_#93;': ']'
    }
    
    for old, new in replacements.items():
        xml_string = xml_string.replace(old, new)

    # --- 2. Parse the Cleaned XML and Extract Data ---
    try:
        root = ET.fromstring(xml_string)
        
        # Find the <Description> tag, which contains the most useful info
        description_tag = root.find('.//Description')
        if description_tag is None:
            return None

        # Extract the full description attribute
        description_text = description_tag.get('Description', '')

        # --- 3. Extract Key Values from the Description Text ---
        # Use regular expressions to find the timepoint and ROI list
        timepoint_match = re.search(r'timepoint: (\d+)', description_text)
        roi_match = re.search(r'ROI: ([\d\s]+)power', description_text)

        timepoint = int(timepoint_match.group(1)) if timepoint_match else None
        
        rois = []
        if roi_match:
            # Split the string of numbers and convert each to an integer
            rois = [int(n) for n in roi_match.group(1).strip().split()]

        return {
            'device_name': root.find('.//Device').get('LongName'),
            'duration_ms': int(root.find('.//Duration').get('Time')),
            'description_text': description_text,
            'event_timepoint_ms': timepoint,
            'stimulated_rois': rois
        }

    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

def extract_roi_info(events):
    all_events_roi_data = []
    
    for event in events:
        event_info = {
        "timepoint_index": event['timepoint_index'],
        "rois": []
        }

        roi_annotations = event['roi_annotations']
        organized_rois = {}

        for i, ann in enumerate(roi_annotations):
            if ann.get('ClassName') == 'CCubeAnnotation70':
                roi_id = ann.get('mRegionIndex')
                if i + 1 < len(roi_annotations):
                    organized_rois[roi_id] = roi_annotations[i + 1]

        for roi_id, roi_data in organized_rois.items():
            # Get the pixel coordinates from StructArrayValues
            coords = roi_data.get('StructArrayValues', [])
            
            # Format the coordinates into two (X, Y) points
            point1 = (coords[0], coords[1], coords[2]) if len(coords) >= 3 else None
            point2 = (coords[3], coords[4], coords[5]) if len(coords) >= 6 else None

            event_info["rois"].append({
                "roi_index": roi_id,
                "target_power": roi_data.get('mTargetPower'),
                "corner_1_xyz": point1,
                "corner_2_xyz": point2
            })
        
        all_events_roi_data.append(event_info)
    return all_events_roi_data

# Read all the files in the folder using yaml

data = {}
for filename in os.listdir(folder_path):
    if filename.endswith(".yaml"):
        if filename in ["ImageRecord.yaml", "ChannelRecord.yaml"]:
            with open(os.path.join(folder_path, filename), 'r') as file:
                try:
                    classes = load_classes(os.path.join(folder_path, filename))
                    data[filename] = classes
                except yaml.YAMLError as e:
                    print(f"Error reading {filename}: {e}")
        elif filename == "AnnotationRecord.yaml":
            try:
                content = get_organized_experiment_data(os.path.join(folder_path, filename))
                data[filename] = content
            except yaml.YAMLError as e:
                print(f"Error reading {filename}: {e}")
        else:
            with open(os.path.join(folder_path, filename), 'r') as file:
                try:
                    content = yaml.safe_load(file)
                    data[filename] = content
                except yaml.YAMLError as e:
                    print(f"Error reading {filename}: {e}")

# Extract date/time values with error handling
try:
    day = data["ImageRecord.yaml"]["CImageRecord70"]["mDay"]
except (KeyError, TypeError):
    day = "NA"

try:
    month = data["ImageRecord.yaml"]["CImageRecord70"]["mMonth"]
except (KeyError, TypeError):
    month = "NA"

try:
    year = data["ImageRecord.yaml"]["CImageRecord70"]["mYear"]
except (KeyError, TypeError):
    year = "NA"

try:
    hour = data["ImageRecord.yaml"]["CImageRecord70"]["mHour"]
except (KeyError, TypeError):
    hour = "NA"

try:
    minute = data["ImageRecord.yaml"]["CImageRecord70"]["mMinute"]
except (KeyError, TypeError):
    minute = "NA"

try:
    second = data["ImageRecord.yaml"]["CImageRecord70"]["mSecond"]
except (KeyError, TypeError):
    second = "NA"

# Helper function to safely extract values
def safe_extract(func, default="NA"):
    """Safely execute a function and return default if it fails."""
    try:
        result = func()
        return result if result is not None else default
    except (KeyError, TypeError, IndexError, AttributeError, ValueError):
        return default

variables = {
    "device_name": safe_extract(lambda: parse_stimulation_xml(data["AnnotationRecord.yaml"]["stimulation_events"][0]["stimulation_data"]["mXML"])["device_name"] if data["AnnotationRecord.yaml"]["stimulation_events"] else "NA"),
    "n_frames": safe_extract(lambda: data["ElapsedTimes.yaml"]["theElapsedTimes"][0]),
    "pixel_size": safe_extract(lambda: data["ImageRecord.yaml"]["CLensDef70"]["mMicronPerPixel"]),
    "height": safe_extract(lambda: data["ImageRecord.yaml"]["CImageRecord70"]["mHeight"]),
    "width": safe_extract(lambda: data["ImageRecord.yaml"]["CImageRecord70"]["mWidth"]),
    "FOV_size": safe_extract(lambda: f"{data['ImageRecord.yaml']['CLensDef70']['mMicronPerPixel'] * data['ImageRecord.yaml']['CImageRecord70']['mHeight']} x {data['ImageRecord.yaml']['CLensDef70']['mMicronPerPixel'] * data['ImageRecord.yaml']['CImageRecord70']['mWidth']} microns"),
    "Elapsed_time_offset": safe_extract(lambda: data["ImageRecord.yaml"]["CImageRecord70"]["mElapsedTimeOffset"]),
    "green_channel": safe_extract(lambda: data["ImageRecord.yaml"]["CMainViewRecord70"]["mGreenChannel"]),
    "red_channel": safe_extract(lambda: data["ImageRecord.yaml"]["CMainViewRecord70"]["mRedChannel"]),
    "blue_channel": safe_extract(lambda: data["ImageRecord.yaml"]["CMainViewRecord70"]["mBlueChannel"]),
    "X_start_position": safe_extract(lambda: data["ChannelRecord.yaml"]["CExposureRecord70"][0]["mXStartPosition"]),
    "Y_start_position": safe_extract(lambda: data["ChannelRecord.yaml"]["CExposureRecord70"][0]["mYStartPosition"]),
    "Z_start_position": safe_extract(lambda: data["ChannelRecord.yaml"]["CExposureRecord70"][0]["mZStartPosition"]),
    "day": day,
    "month": month,
    "year": year,
    "hour": hour,
    "minute": minute,
    "second": second,
    "stimulation_events": safe_extract(lambda: len([x["timepoint_index"] for x in data["AnnotationRecord.yaml"]["stimulation_events"]]), 0),
    "repetitions": safe_extract(lambda: [
        int(re.search(r"(\d+)\s+repetition", parse_stimulation_xml(event["stimulation_data"]["mXML"])["description_text"]).group(1))
        for event in data["AnnotationRecord.yaml"]["stimulation_events"]
    ], []),
    "duty_cycle": safe_extract(lambda: [
        re.search(r"user defined analog:\s+(.*?)\s+1 repetition", parse_stimulation_xml(event["stimulation_data"]["mXML"])["description_text"]).group(1)
        for event in data["AnnotationRecord.yaml"]["stimulation_events"]
    ], []),
    "stimulation_timeframes": safe_extract(lambda: [x["timepoint_index"] for x in data["AnnotationRecord.yaml"]["stimulation_events"]], []),
    "stimulation_ms": safe_extract(lambda: [parse_stimulation_xml(x["stimulation_data"]["mXML"])["event_timepoint_ms"] for x in data["AnnotationRecord.yaml"]["stimulation_events"]], []),
    "duration_ms": safe_extract(lambda: [parse_stimulation_xml(x["stimulation_data"]["mXML"])["duration_ms"] for x in data["AnnotationRecord.yaml"]["stimulation_events"]], []),
    "stimulated_rois": safe_extract(lambda: [parse_stimulation_xml(x["stimulation_data"]["mXML"])["stimulated_rois"] for x in data["AnnotationRecord.yaml"]["stimulation_events"]], []),
    "stimulated_roi_powers": safe_extract(lambda: [
        [(x["roi_index"], x["target_power"]) for x in ev["rois"]] for ev in extract_roi_info(data["AnnotationRecord.yaml"]["stimulation_events"])
    ], []),
    "stimulated_roi_location": safe_extract(lambda: [
        [(x["roi_index"], x["corner_1_xyz"], x["corner_2_xyz"]) for x in ev["rois"]] for ev in extract_roi_info(data["AnnotationRecord.yaml"]["stimulation_events"])
    ], []),
    "time_stamps": safe_extract(lambda: data["ElapsedTimes.yaml"]["theElapsedTimes"][1:], []),
    "initial_roi_powers": safe_extract(lambda: [
        (roi_id, roi_data.get('mTargetPower')) for roi_id, roi_data in data["AnnotationRecord.yaml"]["initial_rois"].items()
    ], []),
    "initial_roi_location": safe_extract(lambda: [
        (roi_id, 
         tuple(roi_data.get('StructArrayValues', [])[0:3]), 
         tuple(roi_data.get('StructArrayValues', [])[3:6])) 
        for roi_id, roi_data in data["AnnotationRecord.yaml"]["initial_rois"].items()
    ], [])
}

print("Saving experiment_summary.csv...")
with open_overwrite(Path(folder_path) / 'experiment_summary.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Parameter', 'Value'])  # Write header
    
    # Loop through the dictionary and save single-value items
    for key, value in variables.items():
        if not isinstance(value, list) and not isinstance(value, np.ndarray):
            writer.writerow([key, value])

print("Saving stimulation_events.csv...")
# Define the headers for our events file
event_headers = [
    'event_index', 
    'timepoint_frame', 
    'timepoint_ms', 
    'duration_ms', 
    'repetitions', 
    'duty_cycle',
    'stimulated_rois'
]

with open_overwrite(Path(folder_path) / 'stimulation_events.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=event_headers)
    writer.writeheader()
    
    # Loop through each of the 3 events to create a row
    for i in range(variables['stimulation_events']):
        writer.writerow({
            'event_index': i + 1,
            'timepoint_frame': variables['stimulation_timeframes'][i],
            'timepoint_ms': variables['stimulation_ms'][i],
            'duration_ms': variables['duration_ms'][i],
            'repetitions': variables['repetitions'][i],
            'duty_cycle': variables['duty_cycle'][i],
            'stimulated_rois': variables['stimulated_rois'][i]
        })

# --- 3. Save the Detailed ROI Data ---
print("Saving roi_details.csv...")
roi_headers = [
    'event_index',
    'roi_index',
    'target_power',
    'corner_1_x',
    'corner_1_y',
    'corner_1_z',
    'corner_2_x',
    'corner_2_y',
    'corner_2_z'
]

with open_overwrite(Path(folder_path) / 'roi_details.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=roi_headers)
    writer.writeheader()
    
    # Nested loop: outer loop for events, inner loop for ROIs within that event
    for i in range(variables['stimulation_events']):
        # Get the power and location data for the current event
        powers = variables['stimulated_roi_powers'][i]
        locations = variables['stimulated_roi_location'][i]
        
        # Create a dictionary for easy lookup: {roi_index: (p1, p2)}
        locations_dict = {loc[0]: (loc[1], loc[2]) for loc in locations}

        # Loop through the list of tuples and unpack them directly
        for roi_id, power in powers: 
            corner1, corner2 = locations_dict.get(roi_id, ((None, None), (None, None)))
            writer.writerow({
                'event_index': i + 1,
                'roi_index': roi_id,
                'target_power': power,
                'corner_1_x': corner1[0] if corner1 else np.nan,
                'corner_1_y': corner1[1] if corner1 else np.nan,
                'corner_1_z': corner1[2] if corner1 else np.nan,
                'corner_2_x': corner2[0] if corner2 else np.nan,
                'corner_2_y': corner2[1] if corner2 else np.nan,
                'corner_2_z': corner2[2] if corner2 else np.nan
            })

with open(Path(folder_path) / 'experiment_summary.pkl', 'wb') as f:
    # 'wb' is used for writing in binary mode
    pickle.dump(variables, f)

# Output a json file 
with open_overwrite(Path(folder_path) / 'experiment_summary.json', 'w', encoding='utf-8') as f:
    json.dump(variables, f, indent=4)

print(f"JSON file and Pickle file saved to {folder_path}")


if variables["Elapsed_time_offset"] != "NA" and variables["Elapsed_time_offset"] != 0:   
    print(f"⚠️ Warning: Elapsed time offset is {variables['Elapsed_time_offset']} ms, not zero as expected.")
if variables["n_frames"] != "NA" and variables["time_stamps"] != "NA" and variables["n_frames"] != len(variables["time_stamps"]):
    print(f"⚠️ Warning: Number of frames ({variables['n_frames']}) does not match length of time stamps ({len(variables['time_stamps'])}).")

print("\n[OK] Files saved successfully.")

